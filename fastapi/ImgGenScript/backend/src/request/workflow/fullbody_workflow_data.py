from dataclasses import dataclass
from .workflow_data import WorkflowData

@dataclass
class FullBodyWorkflowData(WorkflowData):
    """
    Stores all configuration parameters for the full-body ComfyUI workflow.

    This data class extends `WorkflowData` with specific settings for generating
    full-body images, including sampler parameters, ControlNet weights, and
    face restoration model settings.

    Args:
        ref_image (str): Path to the reference pose image within the ComfyUI container.
        k0_seed (int): Seed for the first KSampler pass.
        k0_steps (int): Number of steps for the first KSampler pass.
        k0_cfg (float): CFG scale for the first KSampler pass.
        k0_sampler_name (str): The sampler name for the first KSampler.
        k0_scheduler (str): The scheduler for the first KSampler.
        dwpreprocessor_bbox_detector (str): The bbox detector model for DWPose.
        dwpreprocessor_pose_estimator (str): The pose estimator model for DWPose.
        use_reference_pose (bool): If True, use a reference image for the pose.
        pose_controlnet_model (str): The model name for the pose ControlNet.
        pose_controlnet_weight (float): Weight for the pose ControlNet.
        pose_controlnet_start (float): Start step (as a fraction) for applying pose ControlNet.
        pose_controlnet_end (float): End step (as a fraction) for applying pose ControlNet.
        k1_seed (int): Seed for the first KSampler pass.
        k1_steps (int): Number of steps for the first KSampler pass.
        k1_cfg (float): CFG scale for the first KSampler pass.
        k1_sampler_name (str): The sampler name for the first KSampler.
        k1_scheduler (str): The scheduler for the first KSampler.
        ipadapter_lora_name (str): The LoRA model name for the IPAdapter.
        ipadapter_lora_strength_model (float): The model strength for the IPAdapter LoRA.
        ipadapter_lora_strength_clip (float): The clip strength for the IPAdapter LoRA.
        clip_vision_model (str): The CLIP Vision model name.
        insightface_model_name (str): The model name for the InsightFace loader.
        faceid_loader_preset (str): The preset for the FaceID Unified Loader.
        faceid_loader_lora_strength (float): The LoRA strength for the FaceID Unified Loader.
        faceid_weight (float): Weight for the FaceID model.
        faceid_v2_weight (float): Weight for the FaceID v2 model.
        faceid_weight_type (str): Weight type for FaceID (e.g., 'linear').
        faceid_combine_embeds (str): How to combine embeddings in FaceID.
        faceid_start (float): Start step (as a fraction) for applying FaceID.
        faceid_end (float): End step (as a fraction) for applying FaceID.
        plus_face_loader_preset (str): The preset for the Plus Face Unified Loader.
        plus_face_weight (float): Weight for the Plus Face model.
        plus_face_weight_type (str): Weight type for Plus Face.
        plus_face_combine_embeds (str): How to combine embeddings in Plus Face.
        plus_face_start (float): Start step (as a fraction) for applying Plus Face.
        plus_face_end (float): End step (as a fraction) for applying Plus Face.
        k2_seed (int): Seed for the second KSampler pass (refiner).
        k2_steps (int): Number of steps for the second KSampler pass.
        k2_cfg (float): CFG scale for the second KSampler pass.
        k2_sampler_name (str): The sampler name for the second KSampler.
        k2_scheduler (str): The scheduler for the second KSampler.
        k2_denoise (float): Denoise strength for the second KSampler pass.
        detailer_positive_prompt_template (str): Template for the detailer's positive prompt.
        detailer_negative_prompt_template (str): Template for the detailer's negative prompt.
        detailer_wildcard_prompt_template (str): Template for the detailer's wildcard prompt.
        detailer_bbox_model (str): The bbox detector model for the FaceDetailer.
        detailer_seed (int): Seed for the face detailer KSampler.
        detailer_steps (int): Number of steps for the face detailer.
        detailer_cfg (float): CFG scale for the face detailer.
        detailer_sampler_name (str): The sampler name for the detailer.
        detailer_scheduler (str): The scheduler for the detailer.
        detailer_denoise (float): Denoise strength for the face detailer.
        detailer_feather (int): The feather strength for the detailer.
        detailer_bbox_threshold (float): The threshold for the bbox in the detailer.
        detailer_bbox_dilation (int): The dilation factor for the bbox in the detailer.
        detailer_bbox_crop_factor (float): The crop factor for the bbox in the detailer.
        detailer_drop_size (int): The drop size for the detailer.
        use_hands_refiner (bool): If True, use the hands refiner.
        hands_refiner_mask_bbox_padding (int): The padding for the mask in the hands refiner.
        hands_refiner_mask_type (str): The type of mask for the hands refiner.
        hands_refiner_mask_expand (int): The expansion factor for the mask in the hands refiner.
        hands_refiner_detect_thr (float): The detection threshold for the hands refiner.
        hands_refiner_presence_thr (float): The presence threshold for the hands refiner.
        hands_positive_prompt_template (str): Template for the hand refiner's positive prompt.
        hands_negative_prompt_template (str): Template for the hand refiner's negative prompt.
        hands_refiner_controlnet_model (str): The model name for the hand refiner ControlNet.
        hands_refiner_controlnet_weight (float): The weight for the hand refiner ControlNet.
        hands_refiner_controlnet_start (float): The start percentage for the hand refiner ControlNet.
        hands_refiner_controlnet_end (float): The end percentage for the hand refiner ControlNet.
        hands_refiner_seed (int): The seed for the hand refiner KSampler.
        hands_refiner_steps (int): The number of steps for the hand refiner KSampler.
        hands_refiner_cfg (float): The CFG scale for the hand refiner KSampler.
        hands_refiner_sampler_name (str): The sampler name for the hand refiner KSampler.
        hands_refiner_scheduler (str): The scheduler for the hand refiner KSampler.
        hands_refiner_denoise (float): The denoise strength for the hand refiner KSampler.
    """
    # --- RefImage ---
    ref_image: str

    # --- KSampler 0 ---
    k0_seed: int
    k0_steps: int
    k0_cfg: float
    k0_sampler_name: str
    k0_scheduler: str

    # --- DWPose Preprocessor ---
    dwpreprocessor_bbox_detector: str
    dwpreprocessor_pose_estimator: str

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
    
    # --- Hands Refiner ---
    use_hands_refiner: bool
    hands_refiner_mask_bbox_padding: int
    hands_refiner_mask_type: str
    hands_refiner_mask_expand: int
    hands_refiner_detect_thr: float
    hands_refiner_presence_thr: float
    hands_positive_prompt_template: str
    hands_negative_prompt_template: str
    hands_refiner_controlnet_model: str
    hands_refiner_controlnet_weight: float
    hands_refiner_controlnet_start: float
    hands_refiner_controlnet_end: float
    hands_refiner_seed: int
    hands_refiner_steps: int
    hands_refiner_cfg: float
    hands_refiner_sampler_name: str
    hands_refiner_scheduler: str
    hands_refiner_denoise: float