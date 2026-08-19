import logging
from pathlib import Path
from typing import Dict, Any, Optional, Literal

from backend.src.request import (
    DonorData, AppearanceData, RequestFactory, BaseRequest
)

from backend.src.composition.trait_data_loader import TraitDataLoader
from backend.src.batch.services.composition_builder import CompositionBuilder
from backend.src.batch.services.workflow_builder import WorkflowBuilder
from backend.src.config.settings import Settings, get_settings
from backend.src.utils import get_random_option, ensure_dir

class ProjectProcessor:
    """
    Processes a single project (e.g., 'OVODxxxxx') from start to finish.

    This class encapsulates all the logic required to generate images for one
    specific donor. Its responsibilities include:
    - Building a coherent composition of traits using `CompositionBuilder`.
    - Constructing the appropriate ComfyUI workflow via `WorkflowBuilder`.
    - Executing the asynchronous generation request.
    - Handling optional post-processing of the generated images.
    """
    def __init__(
        self,
        trait_loader: TraitDataLoader,
        prompts: Dict[str, str],
        logger: logging.Logger
    ):
        """
        Initializes the ProjectProcessor.

        Args:
            trait_loader (TraitDataLoader): An instance for loading style and physical traits.
            prompts (Dict[str, str]): A dictionary of loaded prompt templates.
            logger (logging.Logger): A logger for recording process information.
        """
        self.trait_loader: TraitDataLoader = trait_loader
        self.prompts: Dict[str, str] = prompts
    
        self.logger: logging.Logger = logger
        self.settings: Settings = get_settings()

    async def process(
        self,
        project_data: Dict[str, str],
        project_path: Path,
        generation_type: Literal["fullbody", "portrait"],
        use_pose: Optional[bool],
        use_hands_refiner: Optional[bool],
        use_amateur_effect: Optional[bool],
    ) -> bool:
        """
        Processes a single project to generate and save images.

        This is the main method that orchestrates the entire generation pipeline for
        a single donor. It builds the composition, constructs the workflow, executes
        the request, and handles post-processing.

        Args:
            project_data (Dict[str, str]): The donor's data row from the CSV file.
            project_path (Path): The path to the project's root directory (e.g., '.../OVODxxxxx').
            generation_type (Literal["fullbody", "portrait"]): The type of generation to perform.
            use_pose (Optional[bool]): Override for using a reference pose image.
            use_hands_refiner (Optional[bool]): Override for using the hands refiner.
            use_amateur_effect (Optional[bool]): Override for applying the amateur post-processing effect.

        Returns:
            bool: True if the process completed successfully, False otherwise.
        """
        # --- Pre-generation setup ---
        if generation_type not in ["fullbody", "portrait"]:
            raise ValueError(f"Invalid generation_type: {generation_type}")
        
        project_name: str = project_data["vreproID"]
        request_data: Dict[str, Any] = RequestFactory.get_request_data(generation_type)
        generation_settings: Dict[str, Any] = request_data["settings"] # Settings for each generation type
        
        if generation_type == "portrait":
            use_pose = generation_settings.use_reference_pose
            use_hands_refiner = False
            use_amateur_effect = False  # revertido: el bloque de geometria del post-processor parece mover rasgos faciales

        donor_id = project_path.name
        self.logger.info(f"Processing project: {donor_id}")

        try:
            # --- 1. Reference Images ---
            ref_image_name, ref_image_path = "", None
            if use_pose:
                ref_images = [f.name for f in Path(request_data["ref_dir"]).iterdir() if f.suffix.lower() in ('.png', '.jpg', '.jpeg')]
                if ref_images:
                    ref_image_name = get_random_option(ref_images)
                    ref_image_path = str(Path(request_data["ref_dir"]) / ref_image_name)
                else:
                    use_pose = False

            # --- 2. Data Objects ---
            physical = CompositionBuilder.create_physical_traits(project_data, self.logger)

            clothing_style_1 = project_data.get("clothingStyle1", "casual").strip().lower()
            clothing_style_2 = project_data.get("clothingStyle2", "").strip().lower()
            
            clothing_style_1 = clothing_style_1 if clothing_style_1 else "casual"

            style_list = []
            if clothing_style_1:
                style_list.append(clothing_style_1)
            if clothing_style_2:
                style_list.append(clothing_style_2)

            style = CompositionBuilder.create_style_traits(
                clothing_style_1=clothing_style_1,
                clothing_style_2=clothing_style_2,
                trait_loader=self.trait_loader,
                logger=self.logger
            )

            composition_builder: CompositionBuilder = CompositionBuilder(physical, style, self.logger)
            composition: Dict[str, Any] = composition_builder.build(generation_type)

            physical_traits: Dict[str, str] = physical.to_dict()
            physical_traits["hair_type"] = project_data["hairType"]
            physical_traits["hair_length"] = project_data["hairLength"]

            donor_data = DonorData(
                vrepro_id=project_name,
                **physical_traits
            )

            appearance_data = AppearanceData(
                outfit_type=composition.get("outfit_fullbody") if generation_type == "fullbody" else composition.get("outfit_portrait"),
                outfit_color=composition.get("outfit_color"),
                hairstyle_type= project_data.get("hairstyleType").strip() or composition.get("hairstyle"),
                makeup_type=composition.get("makeup")
            )

            scene_kwargs = {
                "expression": project_data.get("expression") or composition.get("expression", ""),
                "lighting": composition.get("lighting", ""),
                "pose": composition.get("pose", "") if (use_pose and generation_type == "fullbody") or not use_pose else "",
                "location": composition.get("location", "") if generation_type == "fullbody" else "",
                "background": composition.get("background", "") if generation_type == "portrait" else "",
                "environment": composition.get("environment", "env_indoor"),
                "light_temperature": composition.get("light_temperature", "light_temp_neutral"),
            }
            scene_data = RequestFactory.create_scene_data(request_data["scene_data_class"], generation_type, **scene_kwargs)
            
            # --- 3. Workflow ---
            workflow_builder = WorkflowBuilder(
                generation_type=generation_type,
                generation_settings=generation_settings,
                prompts=self.prompts,
                use_ref_pose=use_pose and bool(ref_image_name),
                ref_image_name=ref_image_name,
                request_data=request_data,
                logger=self.logger
            )

            workflow_data = workflow_builder.build(use_hands_refiner)

            # --- 4. Request ---
            request: BaseRequest = request_data["request_class"](
                donor_data=donor_data,
                appearance_data=appearance_data,
                scene_data=scene_data,
                workflow_data=workflow_data,
                comfyui_server_address=self.settings.comfyui_server_address,
                fastapi_server_address=self.settings.fastapi_server_address,
                logger=self.logger
            )

            # --- 5. Generation ---
            post_process_args = {
                "style_name": get_random_option(style_list),
                "environment_type": composition["environment"],
                "light_temp": composition["light_temperature"]
            } if use_amateur_effect else None

            output_dir = project_path / generation_type
            ensure_dir(output_dir)

            success = await request.request_async(
                input_dir=project_path,
                ref_img=ref_image_path,
                output_dir=output_dir,
                post_process=use_amateur_effect,
                post_process_args=post_process_args,
                logger=self.logger,
                verbose=self.settings.generation_verbose
            )

            return success
            
        except Exception as e:
            self.logger.error(f"Unexpected error processing {donor_id}: {e}", exc_info=True)
            return False
