from typing import List, Dict, Any

from src.config.settings import get_settings
from backend.src.generator.image_generator import ImageGenerator
from .base_request import BaseRequest
from .scene.fullbody_scene_data import FullBodySceneData
from .workflow.fullbody_workflow_data import FullBodyWorkflowData

SETTINGS = get_settings()

class FullBodyRequest(BaseRequest[FullBodySceneData, FullBodyWorkflowData]):
    """
    A concrete implementation of a request to generate full-body images.
    """
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
            "body_type": self.donor_data.body_type,
            "body_complexion": self.donor_data.body_complexion,
            "bust_type": self.donor_data.bust_type,
            "thigh_type": self.donor_data.thigh_type,
            "skin_tone": self.donor_data.skin_tone,
            "special_characteristics": special_char_text,
            "outfit_type": self.appearance_data.outfit_type,
            "outfit_color": self.appearance_data.outfit_color,
            "hairstyle_type": self.appearance_data.hairstyle_type,
            "makeup_type": self.appearance_data.makeup_type,
            "pose": self.scene_data.pose,
            "expression": self.scene_data.expression,
            "location": self.scene_data.location,
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
            ("7", "seed", self.workflow_data.k0_seed),
            ("7", "steps", self.workflow_data.k0_steps),
            ("7", "cfg", self.workflow_data.k0_cfg),
            ("7", "sampler_name", self.workflow_data.k0_sampler_name),
            ("7", "scheduler", self.workflow_data.k0_scheduler),
            ("9", "bbox_detector", self.workflow_data.dwpreprocessor_bbox_detector),
            ("9", "pose_estimator", self.workflow_data.dwpreprocessor_pose_estimator),
            ("10", "control_net_name", self.workflow_data.pose_controlnet_model),
            ("11", "strength", self.workflow_data.pose_controlnet_weight),
            ("11", "start_percent", self.workflow_data.pose_controlnet_start),
            ("11", "end_percent", self.workflow_data.pose_controlnet_end),
            ("12", "seed", self.workflow_data.k1_seed),
            ("12", "steps", self.workflow_data.k1_steps),
            ("12", "cfg", self.workflow_data.k1_cfg),
            ("12", "sampler_name", self.workflow_data.k1_sampler_name),
            ("12", "scheduler", self.workflow_data.k1_scheduler),
            ("13", "lora_name", self.workflow_data.ipadapter_lora_name),
            ("13", "strength_model", self.workflow_data.ipadapter_lora_strength_model),
            ("13", "strength_clip", self.workflow_data.ipadapter_lora_strength_clip),
            ("14", "directory", self.workflow_data.ref_directory),
            ("16", "clip_name", self.workflow_data.clip_vision_model),
            ("17", "model_name", self.workflow_data.insightface_model_name),
            ("18", "preset", self.workflow_data.faceid_loader_preset),
            ("18", "lora_strength", self.workflow_data.faceid_loader_lora_strength),
            ("19", "weight", self.workflow_data.faceid_weight),
            ("19", "weight_faceidv2", self.workflow_data.faceid_v2_weight),
            ("19", "weight_type", self.workflow_data.faceid_weight_type),
            ("19", "combine_embeds", self.workflow_data.faceid_combine_embeds),
            ("19", "start_at", self.workflow_data.faceid_start),
            ("19", "end_at", self.workflow_data.faceid_end),
            ("20", "preset", self.workflow_data.plus_face_loader_preset),
            ("21", "weight", self.workflow_data.plus_face_weight),
            ("21", "weight_type", self.workflow_data.plus_face_weight_type),
            ("21", "combine_embeds", self.workflow_data.plus_face_combine_embeds),
            ("21", "start_at", self.workflow_data.plus_face_start),
            ("21", "end_at", self.workflow_data.plus_face_end),
            ("22", "seed", self.workflow_data.k2_seed),
            ("22", "steps", self.workflow_data.k2_steps),
            ("22", "cfg", self.workflow_data.k2_cfg),
            ("22", "sampler_name", self.workflow_data.k2_sampler_name),
            ("22", "scheduler", self.workflow_data.k2_scheduler),
            ("22", "denoise", self.workflow_data.k2_denoise),
            ("25", "text", client.built_prompts["detailer_positive_prompt"]),
            ("26", "text", client.built_prompts["detailer_negative_prompt"]),
            ("27", "model_name", self.workflow_data.detailer_bbox_model),
            ("28", "seed", self.workflow_data.detailer_seed),
            ("28", "steps", self.workflow_data.detailer_steps),
            ("28", "cfg", self.workflow_data.detailer_cfg),
            ("28", "sampler_name", self.workflow_data.detailer_sampler_name),
            ("28", "scheduler", self.workflow_data.detailer_scheduler),
            ("28", "denoise", self.workflow_data.detailer_denoise),
            ("28", "wildcard", client.built_prompts["detailer_wildcard_prompt"]),
            ("28", "feather", self.workflow_data.detailer_feather),
            ("28", "bbox_threshold", self.workflow_data.detailer_bbox_threshold),
            ("28", "bbox_dilation", self.workflow_data.detailer_bbox_dilation),
            ("28", "bbox_crop_factor", self.workflow_data.detailer_bbox_crop_factor),
            ("28", "drop_size", self.workflow_data.detailer_drop_size),
            ("32", "mask_bbox_padding", self.workflow_data.hands_refiner_mask_bbox_padding),
            ("32", "mask_type", self.workflow_data.hands_refiner_mask_type),
            ("32", "mask_expand", self.workflow_data.hands_refiner_mask_expand),
            ("32", "detect_thr", self.workflow_data.hands_refiner_detect_thr),
            ("32", "presence_thr", self.workflow_data.hands_refiner_presence_thr),
            ("33", "text", client.built_prompts["hands_positive_prompt"]),
            ("34", "text", client.built_prompts["hands_negative_prompt"]),
            ("35", "control_net_name", self.workflow_data.hands_refiner_controlnet_model),
            ("36", "strength", self.workflow_data.hands_refiner_controlnet_weight),
            ("36", "start_percent", self.workflow_data.hands_refiner_controlnet_start),
            ("36", "end_percent", self.workflow_data.hands_refiner_controlnet_end),
            ("37", "seed", self.workflow_data.hands_refiner_seed),
            ("37", "steps", self.workflow_data.hands_refiner_steps),
            ("37", "cfg", self.workflow_data.hands_refiner_cfg),
            ("37", "sampler_name", self.workflow_data.hands_refiner_sampler_name),
            ("37", "scheduler", self.workflow_data.hands_refiner_scheduler),
            ("37", "denoise", self.workflow_data.hands_refiner_denoise),
            ("40", "filename_prefix", self.donor_data.vrepro_id),
        ]
        return workflow_args

    def _get_structural_changes(self) -> Dict[str, Any]:
        changes = {
            "remove": [],
            "reconnect": []
        }

        if not self.workflow_data.use_reference_pose:
            changes["remove"].extend(["5", "6", "7", "8", "9", "10", "11", "41", "44"])
            changes["reconnect"].extend([
                ("3", 0, "12", "positive"),
                ("4", 0, "12", "negative"),
                ("2", 0, "12", "latent_image")
            ])

        if not self.workflow_data.use_hands_refiner:
            changes["remove"].extend(["30", "31", "32", "33", "34", "35", "36", "37", "38"])
            changes["reconnect"].extend([("29", 0, "39", "image")])

        # Remover nodos de Easy-Use que no cargan correctamente
        changes["remove"].extend(["42", "43"])

        return changes
