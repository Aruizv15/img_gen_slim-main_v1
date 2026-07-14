from typing import List, Dict, Any

from src.config.settings import get_settings
from backend.src.generator.image_generator import ImageGenerator
from .base_request import BaseRequest
from .scene.portrait_scene_data import PortraitSceneData
from .workflow.portrait_workflow_data import PortraitWorkflowData

SETTINGS = get_settings()

class PortraitRequest(BaseRequest[PortraitSceneData, PortraitWorkflowData]):
    def _get_positive_prompt_args(self) -> Dict[str, Any]:
        special_char_text = ""
        if self.donor_data.special_characteristics:
            special_char_text = f"({self.donor_data.special_characteristics}:{SETTINGS.special_characteristics_weight}),"
        args = {
            "age": self.donor_data.age,
            "eye_color": self.donor_data.eye_color,
            "hair_color": self.donor_data.hair_color,
            "hair_type": self.donor_data.hair_type,
            "hair_length": self.donor_data.hair_length,
            "body_complexion": self.donor_data.body_complexion,
            "body_type": self.donor_data.body_type,
            "bust_type": self.donor_data.bust_type,
            "skin_tone": self.donor_data.skin_tone,
            "special_characteristics": special_char_text,
            "hairstyle_type": self.appearance_data.hairstyle_type,
            "outfit_type": self.appearance_data.outfit_type,
            "outfit_color": self.appearance_data.outfit_color,
            "makeup_type": self.appearance_data.makeup_type,
            "expression": self.scene_data.expression,
            "background": self.scene_data.background,
            "lighting": self.scene_data.lighting,
        }
        return args

    def _get_node_values_to_set(self, client: ImageGenerator) -> List[tuple]:
        workflow_args = [
            ("1", "ckpt_name", self.workflow_data.checkpoint),
            ("2", "batch_size", self.workflow_data.batch_size),
            ("3", "text", client.built_prompts["positive_prompt"]),
            ("4", "text", client.built_prompts["negative_prompt"]),
            ("5", "image", self.workflow_data.ref_image if self.workflow_data.ref_image else "example.png"),
            ("7", "seed", 42),
            ("7", "steps", self.workflow_data.k1_steps),
            ("7", "cfg", self.workflow_data.k1_cfg),
            ("7", "sampler_name", self.workflow_data.k1_sampler_name),
            ("7", "scheduler", self.workflow_data.k1_scheduler),
            ("8", "clip_name", self.workflow_data.clip_vision_model),
            ("9", "model_name", self.workflow_data.insightface_model_name),
            ("10", "preset", "FACEID"),
            ("10", "lora_strength", self.workflow_data.faceid_loader_lora_strength),
            ("11", "weight", self.workflow_data.faceid_weight),
            ("11", "weight_faceidv2", self.workflow_data.faceid_v2_weight),
            ("11", "weight_type", "linear"),
            ("11", "combine_embeds", self.workflow_data.faceid_combine_embeds),
            ("11", "start_at", self.workflow_data.faceid_start),
            ("11", "end_at", self.workflow_data.faceid_end),
            ("12", "preset", "STANDARD (medium strength)"),
            ("13", "weight", self.workflow_data.plus_face_weight),
            ("13", "weight_type", "linear"),
            ("13", "combine_embeds", self.workflow_data.plus_face_combine_embeds),
            ("13", "start_at", self.workflow_data.plus_face_start),
            ("13", "end_at", self.workflow_data.plus_face_end),
            ("14", "directory", self.workflow_data.ref_directory),
            ("16", "lora_name", self.workflow_data.ipadapter_lora_name),
            ("16", "strength_model", self.workflow_data.ipadapter_lora_strength_model),
            ("16", "strength_clip", self.workflow_data.ipadapter_lora_strength_clip),
            ("17", "seed", 42),
            ("17", "steps", self.workflow_data.k2_steps),
            ("17", "cfg", self.workflow_data.k2_cfg),
            ("17", "sampler_name", self.workflow_data.k2_sampler_name),
            ("17", "scheduler", self.workflow_data.k2_scheduler),
            ("17", "denoise", self.workflow_data.k2_denoise),
            ("20", "text", client.built_prompts["detailer_positive_prompt"]),
            ("21", "text", client.built_prompts["detailer_negative_prompt"]),
            ("22", "model_name", self.workflow_data.detailer_bbox_model),
            ("23", "seed", 42),
            ("23", "steps", self.workflow_data.detailer_steps),
            ("23", "cfg", self.workflow_data.detailer_cfg),
            ("23", "sampler_name", self.workflow_data.detailer_sampler_name),
            ("23", "scheduler", self.workflow_data.detailer_scheduler),
            ("23", "denoise", self.workflow_data.detailer_denoise),
            ("23", "wildcard", client.built_prompts["detailer_wildcard_prompt"]),
            ("23", "feather", self.workflow_data.detailer_feather),
            ("23", "bbox_threshold", self.workflow_data.detailer_bbox_threshold),
            ("23", "bbox_dilation", self.workflow_data.detailer_bbox_dilation),
            ("23", "bbox_crop_factor", self.workflow_data.detailer_bbox_crop_factor),
            ("23", "drop_size", self.workflow_data.detailer_drop_size),
            ("27", "filename_prefix", self.donor_data.vrepro_id),
        ]
        return workflow_args

    def _get_structural_changes(self) -> Dict[str, Any]:
        changes = {"remove": [], "reconnect": []}
        return changes
