import uuid
import logging
from typing import List, Tuple, Dict, Any, Optional

from ..clients.comfyui_client import ComfyUIClient
from ..clients.fastapi_client import FastAPIClient
from .components.workflow.workflow_manager import WorkflowManager
from .components.builders.prompt_builder import PromptBuilder
from .components.handlers.image_handler import ImageHandler
from .components.handlers.memory_manager import MemoryManager
from .components.post_processor.post_processor import PostProcessor
from src.utils import save_json_file
from src.config.settings import get_settings

SETTINGS = get_settings()

class ImageGenerator:
    """
    A high-level client that orchestrates the entire image generation process.

    This class acts as a facade, integrating multiple clients and managers to
    provide a simplified interface for a complete generation workflow. It handles:
    - Communication with ComfyUI (`ComfyUIClient`) and a FastAPI backend (`FastAPIClient`).
    - Management of workflow templates (`WorkflowManager`).
    - Building and formatting of text prompts (`PromptBuilder`).
    - Handling of image uploads and downloads (`ImageHandler`).
    - Memory and resource cleanup (`MemoryManager`).

    It is designed to be used as a context manager to ensure proper resource cleanup.
    """
    def __init__(
        self,
        comfyui_address: str = SETTINGS.comfyui_server_address,
        fastapi_address: str = SETTINGS.fastapi_server_address,
        workflow_path: Optional[str] = None,
        client_id: Optional[str] = None,
        logger: Optional[logging.Logger] | None = None
    ):
        """
        Initializes the ImageGenerator and its underlying components.

        Args:
            comfyui_address (str): The address of the ComfyUI server (e.g., "127.0.0.1:8188").
            fastapi_address (str): The address of the FastAPI server (e.g., "127.0.0.1:8000").
            workflow_path (str, optional): The file path to the base ComfyUI workflow JSON.
            client_id (str, optional): A unique identifier for the client session. Auto-generated if None.
            logger (logging.Logger, optional): A logger for recording process information.
        """
        self.client_id = client_id or str(uuid.uuid4())

        self.logger = logger

        self.comfy: ComfyUIClient = ComfyUIClient(comfyui_address, client_id=self.client_id, logger=self.logger)
        self.fastapi: FastAPIClient = FastAPIClient(fastapi_address, client_id=self.client_id, logger=self.logger)

        self.workflow: WorkflowManager = WorkflowManager(workflow_path)
        self._prompt_builder: PromptBuilder = PromptBuilder()
        self.images: ImageHandler = ImageHandler(self.comfy, self.fastapi)
        self.memory: MemoryManager = MemoryManager(self.comfy, self.fastapi)
        self.post_processor = PostProcessor(logger=self.logger)

    @property
    def prompt_templates(self) -> Dict[str, str]:
        """Provides read-only access to the loaded prompt templates."""
        return self._prompt_builder.templates
    
    @property
    def built_prompts(self) -> Dict[str, str]:
        """Provides read-only access to the final, formatted prompts."""
        return self._prompt_builder.prompts

    def generate(
        self,
        prompt_config: Dict[str, Dict[str, Any]],
        values_to_set: List[Tuple[str, str, Any]],
        structural_changes: Dict[str, Any],
        input_dir: Optional[str] = None,
        ref_img: Optional[str] = None,
        output_dir: Optional[str] = None,
        post_process: bool = False,
        post_process_args: Optional[Dict[str, Any]] = None
    ) -> List[Tuple[str, bytes]]:
        """
        Executes the full image generation pipeline.

        This method orchestrates the entire process:
        1. Cleans up memory and previous images.
        2. Uploads new input and reference images.
        3. Builds text prompts from templates and arguments.
        4. Configures the ComfyUI workflow with dynamic values and structural changes.
        5. Triggers the generation in ComfyUI and downloads the resulting images.
        6. Applies a post-processing effect if specified.
        7. Performs a final cleanup of memory and temporary files.

        Args:
            prompt_config (Dict[str, Dict[str, Any]]): Configuration for building text prompts.
            values_to_set (List[Tuple[str, str, Any]])): A list of tuples to modify specific inputs in the workflow nodes.
            structural_changes (Dict[str, Any]): A dictionary defining nodes to remove or reconnect.
            input_dir (str, optional): Path to a directory of input images for the workflow.
            ref_img (str, optional): Path to a single reference image (e.g., for pose).
            output_dir (str, optional): Directory to save the generated images.
            post_process (bool, optional): Whether to apply a post-processing effect.
            post_process_args (Dict[str, Any], optional): Additional arguments for the post-processing effect (style_name, environment_type, light_temperature ).

        Returns:
            True if the generation was successful, False otherwise.
        """
        def v(section: str) -> bool:
            return SETTINGS.get_verbose_flag(section)

        try:
            # 1. Memory & Image Cleanup
            self.memory.free_all(unload_models=True, verbose=v("memory"))
            self.images.clear_all(v("images"))

            # 2. Upload
            self.images.upload_images(input_dir, ref_img, verbose=v("images"))

            # 3. Prompts
            self._prompt_builder.build_all(prompt_config)

            # 4. Workflow
            self.workflow.start()
            self.workflow.edit_inputs(values_to_set, v("workflow"))
            self.workflow.edit_structure(verbose=v("workflow"), **structural_changes)
            workflow_dict = self.workflow.get_dict()

            if SETTINGS.save_workflow:
                save_json_file("backend/logs/workflow.json", workflow_dict)

            # 5. Generate
            img_tuple = self.images.generate_images(workflow_dict, v("generation"))
            
            # 6. Download
            raw_images = self.images.download_images(img_tuple, v("images"))
            
            # 7. Post processor
            if post_process:
                processed_images = self.post_processor.process_batch(
                    images=raw_images,
                    verbose=v("post_process"),
                    **post_process_args
                )
            else:
                processed_images = None

            # 8. Save
            self.images.save_images(
                output_dir=output_dir,
                raw_images=raw_images,
                processed_images=processed_images,
                verbose=v("images")
            )

            return True
        
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error during generation: {e}", exc_info=True)
            return False
        
        finally:
            self.memory.free_all(unload_models=True, verbose=v("memory"))
            self.images.clear_all(v("images"))

    def __enter__(self):
        """Enables use of the client as a context manager."""
        return self

    def __exit__(self, *args): self.close()

    def close(self):
        """Closes the underlying HTTP client sessions."""
        self.comfy.http.close()
        self.fastapi.http.close()