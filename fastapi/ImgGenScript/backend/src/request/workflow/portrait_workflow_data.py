from dataclasses import dataclass
from .workflow_data import WorkflowData

@dataclass
class PortraitWorkflowData(WorkflowData):
    """
    Stores all configuration parameters for the portrait ComfyUI workflow.
    """
    # --- RefImage ---
    ref_image: str

    # --- ControlNet Preprocessor ---
    controlnet_preprocessor: str
    controlnet_preprocessor_sd_version: str

    # --- ControlNet ---
    use_reference_pose: bool
    pose_controlnet_model: str
    pose_controlnet_weight: float
    pose_controlnet_start: float
    pose_controlnet_end: float

    # --- KSampler 1 ---
    k1_seed: int
    k1_steps: int
    k1_cfg: float
    k1_sampler_name: str
    k1_scheduler: str

    # --- LoRA Loader ---
    ipadapter_lora_name: str
    ipadapter_lora_strength_model: float
    ipadapter_lora_strength_clip: float

    # --- CLIP Vision Loader ---
    clip_vision_model: str

    # --- Insightface Loader---
    insightface_model_name: str

    # --- IPAdapter - FaceID ---
    faceid_loader_preset: str
    faceid_loader_lora_strength: float
    faceid_weight: float
    faceid_v2_weight: float
    faceid_weight_type: str
    faceid_combine_embeds: str
    faceid_start: float
    faceid_end: float

    # --- Plus Face ---
    plus_face_loader_preset: str
    plus_face_weight: float
    plus_face_weight_type: str
    plus_face_combine_embeds: str
    plus_face_start: float
    plus_face_end: float

    # --- KSampler 2 ---
    k2_seed: int
    k2_steps: int
    k2_cfg: float
    k2_sampler_name: str
    k2_scheduler: str
    k2_denoise: float

    # --- Face Detailer ---
    detailer_positive_prompt_template: str
    detailer_negative_prompt_template: str
    detailer_wildcard_prompt_template: str
    detailer_bbox_model: str
    detailer_seed: int
    detailer_steps: int
    detailer_cfg: float
    detailer_sampler_name: str
    detailer_scheduler: str
    detailer_denoise: float
    detailer_feather: int
    detailer_bbox_threshold: float
    detailer_bbox_dilation: int
    detailer_bbox_crop_factor: float
    detailer_drop_size: int
