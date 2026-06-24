import logging
from pathlib import Path
from typing import Dict, Any
from backend.src.config.settings import Settings, get_settings
from backend.src.utils import make_random_seed

class WorkflowBuilder:
    """
    Constructs the specific WorkflowData object based on the generation type.

    This class encapsulates all the workflow construction logic,
    including common parameters, type-specific parameters (fullbody/portrait),
    and handling of reference images. It acts as a factory for `WorkflowData`
    objects, ensuring that all necessary settings and prompts are correctly
    assembled for a given generation task.
    """

    def __init__(
        self,
        generation_type: str,
        generation_settings: Dict[str, Any],
        prompts: Dict[str, str],
        use_ref_pose: bool,
        ref_image_name: str,
        request_data: Dict[str, Any],
        logger: logging.Logger = None,
    ):
        """
        Initializes the WorkflowBuilder.

        Args:
            generation_type (str): The type of generation ('fullbody' or 'portrait').
            generation_settings (Dict[str, Any]): Type-specific configuration settings (from RequestFactory).
            prompts (Dict[str, str]): A dictionary containing prompt templates.
            use_ref_pose (bool): Whether a reference pose image is being used.
            ref_image_name (str): The filename of the reference image, if `use_ref_pose` is True.
            request_data (Dict[str, Any]): Request data for the specific generation type (from RequestFactory).
            logger (logging.Logger, optional): A logger instance for recording events. Defaults to None.
        """
        if generation_type not in ["fullbody", "portrait"]:
            raise ValueError(f"Unknown generation type: {generation_type}")

        self.generation_type = generation_type
        self.generation_settings = generation_settings
        self.prompts = prompts
        self.use_ref_pose = use_ref_pose
        self.ref_image_name = ref_image_name
        self.request_data = request_data
        self.settings: Settings = get_settings()
        self.logger: logging.Logger = logger

    def build(self, use_hands_refiner: bool = False) -> Any:
        """
        Builds and returns the appropriate WorkflowData object.

        This method assembles all the necessary parameters, including basic,
        common, and type-specific settings, along with prompt templates and
        reference image information, into a structured WorkflowData object.

        Args:
            use_hands_refiner (bool): Whether to enable the hands refiner for fullbody generation.
                                      Defaults to False.

        Returns:
            Any: An instance of a WorkflowData subclass (e.g., FullBodyWorkflowData or PortraitWorkflowData).

        Raises:
            ValueError: If an unknown generation type is provided.
        """
        if self.generation_type not in ["fullbody", "portrait"]:
            raise ValueError(f"Unknown generation type: {self.generation_type}")

        if self.logger:
            self.logger.debug(f"Building workflow for generation type: {self.generation_type}")

        # --- Basic Parameters ---
        basic_args = {
            "checkpoint": self.generation_settings.checkpoint,
            "workflow_path": str(Path(self.settings.workflow_dir) / self.generation_settings.workflow),
            "batch_size": int(self.generation_settings.batch_size),
            "ref_directory": self.settings.comfyui_input_dir,
            "positive_prompt_template": self.prompts["fullbody_positive"] if self.generation_type == "fullbody" else self.prompts["portrait_positive"],
            "negative_prompt_template": self.prompts["negative"],
        }

        # --- Parameters common to fullbody and portrait ---
        common_args = {
            "ref_image": (Path(self.settings.comfyui_reference_dir) / self.ref_image_name).as_posix()
            if self.use_ref_pose and self.ref_image_name else "",
            "use_reference_pose": self.use_ref_pose,
            "pose_controlnet_model": self.generation_settings.pose_controlnet_model,
            "pose_controlnet_weight": float(self.generation_settings.pose_controlnet_weight),
            "pose_controlnet_start": float(self.generation_settings.pose_controlnet_start),
            "pose_controlnet_end": float(self.generation_settings.pose_controlnet_end),
            "k1_seed": int(make_random_seed()),
            "k1_steps": int(self.generation_settings.k1_steps),
            "k1_cfg": float(self.generation_settings.k1_cfg),
            "k1_sampler_name": self.generation_settings.k1_sampler_name,
            "k1_scheduler": self.generation_settings.k1_scheduler,
            "ipadapter_lora_name": self.generation_settings.ipadapter_lora_name,
            "ipadapter_lora_strength_model": float(self.generation_settings.ipadapter_lora_strength_model),
            "ipadapter_lora_strength_clip": float(self.generation_settings.ipadapter_lora_strength_clip),
            "clip_vision_model": self.generation_settings.clip_vision_model,
            "insightface_model_name": self.generation_settings.insightface_model_name,
            "faceid_loader_preset": self.generation_settings.faceid_loader_preset,
            "faceid_loader_lora_strength": float(self.generation_settings.faceid_loader_lora_strength),
            "faceid_weight": float(self.generation_settings.faceid_weight),
            "faceid_v2_weight": float(self.generation_settings.faceid_v2_weight),
            "faceid_weight_type": self.generation_settings.faceid_weight_type,
            "faceid_combine_embeds": self.generation_settings.faceid_combine_embeds,
            "faceid_start": float(self.generation_settings.faceid_start),
            "faceid_end": float(self.generation_settings.faceid_end),
            "plus_face_loader_preset": self.generation_settings.plus_face_loader_preset,
            "plus_face_weight": float(self.generation_settings.plus_face_weight),
            "plus_face_weight_type": self.generation_settings.plus_face_weight_type,
            "plus_face_combine_embeds": self.generation_settings.plus_face_combine_embeds,
            "plus_face_start": float(self.generation_settings.plus_face_start),
            "plus_face_end": float(self.generation_settings.plus_face_end),
            "k2_seed": int(make_random_seed()),
            "k2_steps": int(self.generation_settings.k2_steps),
            "k2_cfg": float(self.generation_settings.k2_cfg),
            "k2_sampler_name": self.generation_settings.k2_sampler_name,
            "k2_scheduler": self.generation_settings.k2_scheduler,
            "k2_denoise": float(self.generation_settings.k2_denoise),
            "detailer_positive_prompt_template": self.prompts["detailer_positive"],
            "detailer_negative_prompt_template": self.prompts["detailer_negative"],
            "detailer_wildcard_prompt_template": self.prompts["detailer_wildcard"],
            "detailer_bbox_model": self.generation_settings.detailer_bbox_model,
            "detailer_seed": int(make_random_seed()),
            "detailer_steps": int(self.generation_settings.detailer_steps),
            "detailer_cfg": float(self.generation_settings.detailer_cfg),
            "detailer_sampler_name": self.generation_settings.detailer_sampler_name,
            "detailer_scheduler": self.generation_settings.detailer_scheduler,
            "detailer_denoise": float(self.generation_settings.detailer_denoise),
            "detailer_feather": int(self.generation_settings.detailer_feather),
            "detailer_bbox_threshold": float(self.generation_settings.detailer_bbox_threshold),
            "detailer_bbox_dilation": int(self.generation_settings.detailer_bbox_dilation),
            "detailer_bbox_crop_factor": float(self.generation_settings.detailer_bbox_crop_factor),
            "detailer_drop_size": int(self.generation_settings.detailer_drop_size),
        }

        # --- Type-specific Parameters ---
        specific_args = {}

        if self.generation_type == "fullbody":
            specific_args.update({
                "k0_seed": int(make_random_seed()),
                "k0_steps": int(self.generation_settings.k0_steps),
                "k0_cfg": float(self.generation_settings.k0_cfg),
                "k0_sampler_name": self.generation_settings.k0_sampler_name,
                "k0_scheduler": self.generation_settings.k0_scheduler,
                "dwpreprocessor_bbox_detector": self.generation_settings.dwpreprocessor_bbox_detector,
                "dwpreprocessor_pose_estimator": self.generation_settings.dwpreprocessor_pose_estimator,
                "use_hands_refiner": use_hands_refiner,
                "hands_refiner_mask_bbox_padding": int(self.generation_settings.hands_refiner_mask_bbox_padding),
                "hands_refiner_mask_type": self.generation_settings.hands_refiner_mask_type,
                "hands_refiner_mask_expand": int(self.generation_settings.hands_refiner_mask_expand),
                "hands_refiner_detect_thr": float(self.generation_settings.hands_refiner_detect_thr),
                "hands_refiner_presence_thr": float(self.generation_settings.hands_refiner_presence_thr),
                "hands_positive_prompt_template": self.prompts["hands_positive"],
                "hands_negative_prompt_template": self.prompts["hands_negative"],
                "hands_refiner_controlnet_model": self.generation_settings.hands_refiner_controlnet_model,
                "hands_refiner_controlnet_weight": float(self.generation_settings.hands_refiner_controlnet_weight),
                "hands_refiner_controlnet_start": float(self.generation_settings.hands_refiner_controlnet_start),
                "hands_refiner_controlnet_end": float(self.generation_settings.hands_refiner_controlnet_end),
                "hands_refiner_seed": int(make_random_seed()),
                "hands_refiner_steps": int(self.generation_settings.hands_refiner_steps),
                "hands_refiner_cfg": float(self.generation_settings.hands_refiner_cfg),
                "hands_refiner_sampler_name": self.generation_settings.hands_refiner_sampler_name,
                "hands_refiner_scheduler": self.generation_settings.hands_refiner_scheduler,
                "hands_refiner_denoise": float(self.generation_settings.hands_refiner_denoise),
            })

        elif self.generation_type == "portrait":
            specific_args.update({
                "controlnet_preprocessor": self.generation_settings.controlnet_preprocessor,
                "controlnet_preprocessor_sd_version": self.generation_settings.controlnet_preprocessor_sd_version,
            })

        # --- Build and return WorkflowData ---
        workflow_class = self.request_data["workflow_data_class"]

        if self.logger:
            self.logger.debug(f"Successfully built workflow data with class: {workflow_class.__name__}")

        return workflow_class(**basic_args, **common_args, **specific_args)