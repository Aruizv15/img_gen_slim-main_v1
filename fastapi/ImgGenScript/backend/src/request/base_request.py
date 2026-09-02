import time
import asyncio
import logging

from dataclasses import dataclass
from typing import List, Tuple, Dict, Any, TypeVar, Generic, Optional
from abc import ABC, abstractmethod

from src.config.settings import get_settings
from backend.src.generator.image_generator import ImageGenerator
from .data.donor_data import DonorData
from .data.appearance_data import AppearanceData
from .scene.scene_data import SceneData
from .workflow.workflow_data import WorkflowData

SETTINGS = get_settings()

SceneDataType = TypeVar('SceneDataType', bound=SceneData)
WorkflowDataType = TypeVar('WorkflowDataType', bound=WorkflowData)

class BaseRequest(Generic[SceneDataType, WorkflowDataType], ABC):
    """
    An abstract base class for an image generation request.

    This class defines the common structure and logic for all specific request
    types (e.g., FullbodyRequest, PortraitRequest). It uses generics to allow
    for different types of scene and workflow data while enforcing a consistent
    interface for preparing and executing a ComfyUI workflow.

    It orchestrates the process of:
        1.  Creating prompts from templates and dynamic arguments.
        2.  Building a list of arguments to modify the ComfyUI workflow.
        3.  Applying any final modifications to the workflow structure.
        4.  Executing the generation request via the ComfyUI client.

    Attributes:
        donor_data (DonorData): Data related to the subject (donor).
        appearance_data (AppearanceData): Data for appearance (clothing, hairstyle, etc.).
        scene_data (SceneDataType): Data for the scene (pose, lighting, etc.).
        workflow_data (WorkflowDataType): Configuration data for the workflow.
        comfyui_server_address (str): The address of the ComfyUI server (e.g., "127.0.0.1:8188").
        fastapi_server_address (str): The address of the FastAPI server (e.g., "127.0.0.1:8000").
        logger (logging.Logger, optional): A logger for recording process information.
    """
    def __init__(
        self,
        donor_data: DonorData,
        appearance_data: AppearanceData,
        scene_data: SceneDataType,
        workflow_data: WorkflowDataType,
        comfyui_server_address: str,
        fastapi_server_address: str,
        logger: logging.Logger | None = None,
    ):
        self.donor_data = donor_data
        self.appearance_data = appearance_data
        self.scene_data = scene_data
        self.workflow_data = workflow_data
        self.comfyui_server_address = comfyui_server_address
        self.fastapi_server_address = fastapi_server_address
        self.logger = logger

        self.generator: ImageGenerator = self._setup_generator()
        self._build_prompts()

    def _setup_generator(self) -> ImageGenerator:
        """Create an instance of ImageGenerator for this request."""
        return ImageGenerator(
            comfyui_address=self.comfyui_server_address,
            fastapi_address=self.fastapi_server_address,
            workflow_path=self.workflow_data.workflow_path,
            logger=self.logger,
        )

    def _build_prompts(self) -> None:
        """Configure all prompt templates and build them."""
        pb = self.generator._prompt_builder

        # Main templates
        pb.add("positive_prompt", self.workflow_data.positive_prompt_template)
        pb.add("negative_prompt", self.workflow_data.negative_prompt_template)
        pb.add("detailer_positive_prompt", self.workflow_data.detailer_positive_prompt_template)
        pb.add("detailer_negative_prompt", self.workflow_data.detailer_negative_prompt_template)
        pb.add("detailer_wildcard_prompt", self.workflow_data.detailer_wildcard_prompt_template)

        # Optional templates (hands refiner)
        if hasattr(self.workflow_data, "hands_positive_prompt_template"):
            pb.add("hands_positive_prompt", self.workflow_data.hands_positive_prompt_template)
        if hasattr(self.workflow_data, "hands_negative_prompt_template"):
            pb.add("hands_negative_prompt", self.workflow_data.hands_negative_prompt_template)

        # Build prompts with dynamic args
        prompt_config = {
            "positive_prompt": {"args": self._get_positive_prompt_args(), "in_depth": True},
            "negative_prompt": {"args": self._get_negative_prompt_args()},
            "detailer_positive_prompt": {"args": self._get_detailer_positive_prompt_args()},
            "detailer_negative_prompt": {"args": self._get_detailer_negative_prompt_args()},
            "detailer_wildcard_prompt": {"args": self._get_detailer_wildcard_prompt_args()},
        }

        if "hands_positive_prompt" in pb.templates:
            prompt_config["hands_positive_prompt"] = {"args": self._get_hands_positive_prompt_args()}
        if "hands_negative_prompt" in pb.templates:
            prompt_config["hands_negative_prompt"] = {"args": self._get_hands_negative_prompt_args()}

        pb.build_all(prompt_config)

    @abstractmethod
    def _get_positive_prompt_args(self) -> Dict[str, Any]:
        """
        Returns the arguments for the positive prompt template.

        This abstract method must be implemented by subclasses to provide the
        specific dictionary of arguments needed to format the positive prompt.
        """
        pass

    def _get_negative_prompt_args(self) -> Dict[str, Any]:
        """
        Returns the arguments for the negative prompt template.

        Returns:
            A dictionary of arguments for the negative prompt. Defaults to empty.
        """
        return {}

    def _get_detailer_positive_prompt_args(self) -> Dict[str, Any]:
        """
        Returns the arguments for the detailer's positive prompt template.

        Returns:
            A dictionary of common arguments for the detailer's positive prompt.
        """
        special_char_text = ""
        if self.donor_data.special_characteristics:
            special_char_text = f"({self.donor_data.special_characteristics}:{SETTINGS.special_characteristics_weight}),"

        return {
            "eye_color": self.donor_data.eye_color,
            "expression": self.scene_data.expression,
            "makeup_type": self.appearance_data.makeup_type,
            "special_characteristics": special_char_text,
        }

    def _get_detailer_negative_prompt_args(self) -> Dict[str, Any]:
        """
        Returns the arguments for the detailer's negative prompt template.

        Returns:
            A dictionary of arguments for the detailer's negative prompt. Defaults to empty.
        """
        return {}
    
    def _get_detailer_wildcard_prompt_args(self) -> Dict[str, Any]:
        """
        Returns the arguments for the detailer's wildcard prompt template.

        Returns:
            A dictionary of arguments for the detailer's wildcard prompt. Defaults to empty.
        """
        return {}

    def _get_hands_positive_prompt_args(self) -> Dict[str, Any]:
        """
        Returns the arguments for the hands refiner's positive prompt template.

        Returns:
            A dictionary of arguments for the hands refiner's positive prompt. Defaults to empty.
        """
        return {}

    def _get_hands_negative_prompt_args(self) -> Dict[str, Any]:
        """
        Returns the arguments for the hands refiner's negative prompt template.

        Returns:
            A dictionary of arguments for the hands refiner's negative prompt. Defaults to empty.
        """
        return {}

    @abstractmethod
    def _get_node_values_to_set(self, client: ImageGenerator) -> List[tuple]:
        """
        Returns a list of tuples defining specific input values to set on workflow nodes.

        This abstract method must be implemented by subclasses to provide the
        list of node input value overrides (e.g., sampler seed, text prompts).

        Returns:
            A list of tuples with the format (node_id, input_name, value).
            `(node_id: str, input_name: str, value: Any)`
            where:
            - `node_id` is the ID of the node to modify.
            - `input_name` is the name of the input field to change.
            - `value` is the new value for that input.
        """
        pass

    @abstractmethod
    def _get_structural_changes(self) -> Dict[str, Any]:
        """
        Returns a dictionary of structural modifications to be applied to the ComfyUI workflow.

        This abstract method allows subclasses to define which nodes to remove or which
        connections to change before the workflow is executed.

        Returns:
            A dictionary containing the keys 'remove' and 'reconnect':
            {
                "remove": List[str],
                "reconnect": List[tuple]
            }
            where:
            - `"remove"`: A list of `str` (node IDs) to be removed from the workflow.
            - `"reconnect"`: A list of tuples for connection changes:
            `(from_node: str, from_out: int, to_node: str, to_input: int)`
            (Note: `from_out` and `to_input` are typically 0-indexed port numbers).
        """
        pass

    def _run_sync_generation(
        self,
        input_dir: str,
        ref_img: str,
        output_dir: str,
        post_process: bool = False,
        post_process_args: Optional[Dict[str, Any]] = None,
        verbose: bool = False,
    ) -> List[Tuple[str, bytes]]:
        """
        Internal synchronous helper that contains the generation logic.

        Args:
            input_dir (str): Path to input images directory.
            ref_img (str): Path to reference image.
            output_dir (str): Path to output directory.
            post_process (bool): Whether to apply a post-processing effect.
            post_process_args (Dict[str, Any]): Additional arguments for the post-processing effect

        Returns:
            True if the generation was successful, False otherwise.
        """
        with self.generator:
            values_to_set = self._get_node_values_to_set(self.generator)
            structural_changes = self._get_structural_changes()

            # DEBUG temporal: confirmar en el log el valor EXACTO de eye_color
            # que llega en este punto, para descartar de una vez si el problema
            # es que llega vacio/None/con un valor inesperado.
            if self.logger:
                self.logger.info(
                    f"[EYE_COLOR] donor_data.eye_color = {self.donor_data.eye_color!r} "
                    f"(vrepro_id={getattr(self.donor_data, 'vrepro_id', '?')})"
                )

            return self.generator.generate(
                prompt_config={},
                values_to_set=values_to_set,
                structural_changes=structural_changes,
                input_dir=input_dir,
                ref_img=ref_img,
                output_dir=output_dir,
                post_process=post_process,
                post_process_args=post_process_args,
                # Corrección determinística de color de ojos: independiente
                # del flag post_process (portrait siempre lo tiene en False,
                # pero igual necesita el color correcto). Se pasa siempre
                # que la donante tenga un eye_color definido en el CSV.
                eye_color=self.donor_data.eye_color,
            )
        
    def request(
            self,
            input_dir: str,
            ref_img: str = None,
            output_dir: str = None,
            post_process: bool = False,
            post_process_args: Optional[Dict[str, Any]] = None,
            logger: logging.Logger = None,
            verbose: bool = False
        ) -> bool:
        """
        Executes the full image generation process for this request (synchronous version).

        Args:
            input_dir (str): The path to the directory containing the subject's input images.
            ref_img (str, optional): The path to a single reference image (e.g., for pose), if applicable.
            output_dir (str): Path to output directory.
            post_process (bool): Whether to apply a post-processing effect.
            post_process_args (Dict[str, Any]): Additional arguments for the post-processing effect
            logger (logging.Logger, optional): External logger to use. If ``None``, falls back to module logger.
            verbose (bool, optional): Whether to print detailed progress.

        Returns:
            True if the generation was successful, False otherwise.
        """
        donor_id = self.donor_data.vrepro_id

        if logger:
            logger.info(f"[SYNC GENERATION START] Donor {donor_id}")
        start = time.time()

        try:
            success = self._run_sync_generation(
                input_dir,
                ref_img,
                output_dir=output_dir,
                post_process=post_process,
                post_process_args=post_process_args,
                verbose=verbose
            )
            duration = time.time() - start
            if logger:
                logger.info(f"[SYNC GENERATION END] generated in {duration:.1f}s")
            return success
        except Exception as e:
            duration = time.time() - start
            if logger:
                logger.error(f"[SYNC GENERATION FAILED] Donor {donor_id} after {duration:.1f}s: {e}", exc_info=True)
            return False

    async def request_async(
            self,
            input_dir: str,
            ref_img: str = None,
            output_dir: str = None,
            post_process: bool = False,
            post_process_args: Optional[Dict[str, Any]] = None,
            logger: logging.Logger = None,
            verbose: bool = False
        ) -> bool:
        """
        Executes the full image generation process with timeout and automatic interruption (asynchronous version).

        Args:
            input_dir (str): The path to the directory containing the subject's input images.
            ref_img (str, optional): The path to a single reference image (e.g., for pose), if applicable.
            output_dir (str): Path to output directory.
            post_process (bool): Whether to apply a post-processing effect.
            post_process_args (Dict[str, Any]): Additional arguments for the post-processing effect
            logger (logging.Logger, optiona): Optional external logger for internal use.
            verbose (bool, optional): Whether to print detailed progress.
            
        Returns:
            True if the generation was successful, False otherwise.
        """
        donor_id = self.donor_data.vrepro_id

        timeout = get_settings().interrupt_after_seconds + 30  # 30-second grace period
        if logger:
            logger.info(f"[ASYNC GENERATION START] Donor {donor_id}")

        start = time.time()

        try:
            success = await asyncio.wait_for(
            asyncio.to_thread(
                self._run_sync_generation,
                    input_dir,
                    ref_img,
                    output_dir,
                    post_process,
                    post_process_args,
                    verbose
                ),
            timeout=timeout,
            )
            duration = time.time() - start
            if logger:
                logger.info(f"[ASYNC GENERATION END] generated in {duration:.1f}s")
            return success

        except asyncio.TimeoutError:
            duration = time.time() - start
            if logger:
                logger.warning(f"[GENERATION TIMEOUT] Donor {donor_id} after {duration:.1f}s — interrupting ComfyUI")
            try:
                self.generator.comfy.interrupt_generation(verbose=verbose)
                await asyncio.sleep(2)
            except Exception as e:
                if logger:
                    logger.error(f"[GENERATION INTERRUPTION FAILED]: {e}", exc_info=True)
            finally:
                self.generator.memory.free_all(unload_models=True, verbose=verbose)
            return False

        except Exception as e:
            duration = time.time() - start
            if logger:
                logger.error(f"[GENERATION FAILED] Donor {donor_id} after {duration:.1f}s: {e}", exc_info=True)
            return False
