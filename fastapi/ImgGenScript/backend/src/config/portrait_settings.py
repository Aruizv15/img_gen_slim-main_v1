from pydantic import Field
from pydantic_settings import BaseSettings

class PortraitSettings(BaseSettings):
    """
    Configuration settings for portrait image generation.

    This class encapsulates all the parameters specific to the portrait batch
    process, including workflow details, generation steps, and ControlNet
    settings.

    Attributes:
        workflow (str): The name of the ComfyUI workflow file for portraits.
        checkpoint (str): The name of the checkpoint model to use (.safetensors).
        batch_size (int): The number of images to generate in a single batch.
        controlnet_preprocessor (str): The preprocessor for the pose ControlNet.
        controlnet_preprocessor_sd_version (str): The SD version for the preprocessor.
        pose_controlnet_model (str): The model name for the pose ControlNet.
        pose_controlnet_weight (float): The weight for the pose ControlNet.
        pose_controlnet_start (float): The start percentage for the pose ControlNet.
        pose_controlnet_end (float): The end percentage for the pose ControlNet.
        k1_steps (int): The number of steps for the first KSampler.
        k1_cfg (float): The CFG scale for the first KSampler.
        k1_sampler_name (str): The sampler name for the first KSampler.
        k1_scheduler (str): The scheduler for the first KSampler.
        ipadapter_lora_name (str): The LoRA model name for the IPAdapter.
        ipadapter_lora_strength_model (float): The model strength for the IPAdapter LoRA.
        ipadapter_lora_strength_clip (float): The clip strength for the IPAdapter LoRA.
        clip_vision_model (str): The CLIP Vision model name.
        insightface_model_name (str): The model name for the InsightFace loader.
        faceid_loader_preset (str): The preset for the FaceID Unified Loader.
        faceid_loader_lora_strength (float): The LoRA strength for the FaceID Unified Loader.
        faceid_weight (float): The weight of the FaceID model.
        faceid_v2_weight (float): The weight of the FaceID V2 model.
        faceid_weight_type (str): The type of weight for the FaceID model.
        faceid_combine_embeds (str): The method to combine FaceID embeddings.
        faceid_start (float): The start percentage for the FaceID model.
        faceid_end (float): The end percentage for the FaceID model.
        plus_face_loader_preset (str): The preset for the Plus Face Unified Loader.
        plus_face_weight (float): The weight of the Plus Face model.
        plus_face_weight_type (str): The type of weight for the Plus Face model.
        plus_face_combine_embeds (str): The method to combine Plus Face embeddings.
        plus_face_start (float): The start percentage for the Plus Face model.
        plus_face_end (float): The end percentage for the Plus Face model.
        k2_steps (int): The number of steps for the second KSampler.
        k2_cfg (float): The CFG scale for the second KSampler.
        k2_sampler_name (str): The sampler name for the second KSampler.
        k2_scheduler (str): The scheduler for the second KSampler.
        k2_denoise (float): The denoise strength for the second KSampler.
        detailer_bbox_model (str): The bbox detector model for the FaceDetailer.
        detailer_steps (int): The number of steps for the detailer.
        detailer_cfg (float): The CFG scale for the detailer.
        detailer_sampler_name (str): The sampler name for the detailer.
        detailer_scheduler (str): The scheduler for the detailer.
        detailer_denoise (float): The denoise strength for the detailer.
        detailer_feather (int): The feather strength for the detailer.
        detailer_bbox_threshold (float): The threshold for the bbox in the detailer.
        detailer_bbox_dilation (int): The dilation factor for the bbox in the detailer.
        detailer_bbox_crop_factor (float): The crop factor for the bbox in the detailer.
        detailer_drop_size (int): The drop size for the detailer.
    """
    # --- Workflow ---
    workflow: str

    # --- Checkpoint ---
    checkpoint: str

    # --- Batch Size ---
    batch_size: int

    # --- ControlNet Preprocessor ---
    controlnet_preprocessor: str
    controlnet_preprocessor_sd_version: str

    # --- Pose ControlNet ---
    use_reference_pose: bool
    pose_controlnet_model: str
    pose_controlnet_weight: float
    pose_controlnet_start: float
    pose_controlnet_end: float

    # --- KSampler 1 ---
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
    k2_steps: int
    k2_cfg: float
    k2_sampler_name: str
    k2_scheduler: str
    k2_denoise: float

    # --- Face Detailer ---
    detailer_bbox_model: str
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