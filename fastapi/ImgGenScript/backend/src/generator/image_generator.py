import uuid
import logging
import os
import importlib.util
from typing import List, Tuple, Dict, Any, Optional

from ..clients.comfyui_client import ComfyUIClient
from ..clients.fastapi_client import FastAPIClient
from .components.workflow.workflow_manager import WorkflowManager
from .components.builders.prompt_builder import PromptBuilder
from .components.handlers.image_handler import ImageHandler
from .components.handlers.memory_manager import MemoryManager
from .components.post_processor.post_processor import PostProcessor

_module_logger = logging.getLogger(__name__)


_EYE_COLOR_MODULE_PATH = os.getenv(
    "EYE_COLOR_CORRECTION_PATH",
    "/app/eye_color_correction.py",
)


def _load_correct_eye_color():
    try:
        if not os.path.exists(_EYE_COLOR_MODULE_PATH):
            _module_logger.error(
                f"[EYE_COLOR] No se encontro eye_color_correction.py en "
                f"{_EYE_COLOR_MODULE_PATH}. La correccion de ojos quedara "
                f"DESACTIVADA para esta corrida, pero la generacion sigue normal."
            )
            return None
        spec = importlib.util.spec_from_file_location("eye_color_correction", _EYE_COLOR_MODULE_PATH)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _module_logger.info(f"[EYE_COLOR] Modulo cargado correctamente desde {_EYE_COLOR_MODULE_PATH}")
        return module.correct_eye_color
    except Exception as e:
        _module_logger.error(
            f"[EYE_COLOR] Error cargando eye_color_correction.py desde "
            f"{_EYE_COLOR_MODULE_PATH}: {e}. La correccion de ojos quedara "
            f"DESACTIVADA para esta corrida, pero la generacion sigue normal.",
            exc_info=True,
        )
        return None


_correct_eye_color_fn = _load_correct_eye_color()


def correct_eye_color(image_bytes: bytes, target_color: str):

    if _correct_eye_color_fn is None:
        return None
    return _correct_eye_color_fn(image_bytes, target_color)


from src.utils import save_json_file
from src.config.settings import get_settings

SETTINGS = get_settings()

class ImageGenerator:
 
    def __init__(
        self,
        comfyui_address: str = SETTINGS.comfyui_server_address,
        fastapi_address: str = SETTINGS.fastapi_server_address,
        workflow_path: Optional[str] = None,
        client_id: Optional[str] = None,
        logger: Optional[logging.Logger] | None = None
    ):
        
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

    def _apply_eye_color_correction(
        self,
        images: List[Tuple[str, bytes]],
        eye_color: str,
        verbose: bool = False,
    ) -> List[Tuple[str, bytes]]:
       
        if not eye_color:
            return images

        corrected_list = []
        n_corrected = 0
        for filename, img_bytes in images:
            try:
                corrected_bytes = correct_eye_color(img_bytes, eye_color)
            except Exception as e:
                corrected_bytes = None
                if self.logger:
                    self.logger.error(f"[EYE_COLOR] Excepcion corrigiendo {filename}: {e}", exc_info=True)

            if corrected_bytes is not None:
                corrected_list.append((filename, corrected_bytes))
                n_corrected += 1
            else:
                corrected_list.append((filename, img_bytes))

        if self.logger and verbose:
            self.logger.info(f"[EYE_COLOR] Corregidas {n_corrected}/{len(images)} imagenes (color objetivo: {eye_color})")

        return corrected_list

    def generate(
        self,
        prompt_config: Dict[str, Dict[str, Any]],
        values_to_set: List[Tuple[str, str, Any]],
        structural_changes: Dict[str, Any],
        input_dir: Optional[str] = None,
        ref_img: Optional[str] = None,
        output_dir: Optional[str] = None,
        post_process: bool = False,
        post_process_args: Optional[Dict[str, Any]] = None,
        eye_color: Optional[str] = None,
    ) -> List[Tuple[str, bytes]]:
       
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

       
            if eye_color:
                raw_images = self._apply_eye_color_correction(raw_images, eye_color, verbose=v("images"))
                if processed_images is not None:
                    processed_images = self._apply_eye_color_correction(processed_images, eye_color, verbose=v("images"))

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
