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

    This class specializes the `BaseRequest` to handle the specific requirements
    of generating full-body images. It defines how to assemble the positive
    prompt arguments, which workflow arguments to set, and how to modify the
    workflow structure (e.g., by removing pose-related nodes if not needed).
    """
    def _get_positive_prompt_args(self) -> Dict[str, Any]:
        """
        Assembles the arguments for the positive prompt template.

        Returns:
            A dictionary containing all the dynamic values needed to format
            the full-body positive prompt.
        """
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
        """
        Builds the list of arguments to modify the ComfyUI workflow nodes.

        Args:
            client (ImageGenerator): The ImageGenerator instance, used to access the formatted
                prompt strings.

        Returns:
            A list of tuples, where each tuple represents a specific node input
            to be modified in the workflow (node_id, input_name, value).
        """
        workflow_args = [
            # node_id, input_name, new_value
            ("1", "ckpt_name", self.workflow_data.checkpoint), # Checkpoint Model

            ("2", "batch_size", self.workflow_data.batch_size), # Tamaño del lote

            ("3", "text", client.built_prompts["positive_prompt"]), # Prompt Positivo
            ("4", "text", client.built_prompts["negative_prompt"]), # Prompt Negativo

            ("5", "image", self.workflow_data.ref_image), # Nodo de carga de imagen principal (referencia)

            ("7", "seed", self.workflow_data.k0_seed), # Semilla del primer Ksampler
            ("7", "steps", self.workflow_data.k0_steps), # Pasos del primer Ksampler
            ("7", "cfg", self.workflow_data.k0_cfg), # CFG del primer Ksampler
            ("7", "sampler_name", self.workflow_data.k0_sampler_name), # Sampler del primer Ksampler
            ("7", "scheduler", self.workflow_data.k0_scheduler), # Scheduler del primer Ksampler

            ("9", "bbox_detector", self.workflow_data.dwpreprocessor_bbox_detector), # DWPose bbox_detector
            ("9", "pose_estimator", self.workflow_data.dwpreprocessor_pose_estimator), # DWPose pose_estimator

            ("10", "control_net_name", self.workflow_data.pose_controlnet_model), # Modelo de ControlNet de pose

            ("11", "strength", self.workflow_data.pose_controlnet_weight), # Peso de ControlNet de pose
            ("11", "start_percent", self.workflow_data.pose_controlnet_start), # Inicio de ControlNet de pose
            ("11", "end_percent", self.workflow_data.pose_controlnet_end), # Fin de ControlNet de pose

            ("12", "seed", self.workflow_data.k1_seed), # Semilla del primer Ksampler
            ("12", "steps", self.workflow_data.k1_steps), # Pasos del primer Ksampler
            ("12", "cfg", self.workflow_data.k1_cfg), # CFG del primer Ksampler
            ("12", "sampler_name", self.workflow_data.k1_sampler_name), # Sampler del primer Ksampler
            ("12", "scheduler", self.workflow_data.k1_scheduler), # Scheduler del primer Ksampler

            ("13", "lora_name", self.workflow_data.ipadapter_lora_name), # LoRA IPAdapter
            ("13", "strength_model", self.workflow_data.ipadapter_lora_strength_model), # Fuerza de modelo de LoRA
            ("13", "strength_clip", self.workflow_data.ipadapter_lora_strength_clip), # Fuerza de clip de LoRA

            ("14", "directory", self.workflow_data.ref_directory), # Directorio para el nodo 11 (Load Image)

            ("16", "clip_name", self.workflow_data.clip_vision_model), # Modelo de CLIP Vision

            ("17", "model_name", self.workflow_data.insightface_model_name), # Modelo de InsightFace

            ("18", "preset", self.workflow_data.faceid_loader_preset), # Preset de FaceID Loader
            ("18", "lora_strength", self.workflow_data.faceid_loader_lora_strength), # Fuerza de LoRA de FaceID Loader

            ("19", "weight", self.workflow_data.faceid_weight), # Peso de FaceID
            ("19", "weight_faceidv2", self.workflow_data.faceid_v2_weight), # Peso de FaceID v2
            ("19", "weight_type", self.workflow_data.faceid_weight_type), # Tipo de peso de FaceID
            ("19", "combine_embeds", self.workflow_data.faceid_combine_embeds), # Combinación de embeds de FaceID
            ("19", "start_at", self.workflow_data.faceid_start), # Inicio de FaceID
            ("19", "end_at", self.workflow_data.faceid_end), # Fin de FaceID

            ("20", "preset", self.workflow_data.plus_face_loader_preset), # Preset de Plus Face Loader

            ("21", "weight", self.workflow_data.plus_face_weight), # Peso de Plus Face
            ("21", "weight_type", self.workflow_data.plus_face_weight_type), # Tipo de peso de Plus Face
            ("21", "combine_embeds", self.workflow_data.plus_face_combine_embeds), # Combinación de embeds de Plus Face
            ("21", "start_at", self.workflow_data.plus_face_start), # Inicio de Plus Face
            ("21", "end_at", self.workflow_data.plus_face_end), # Fin de Plus Face

            ("22", "seed", self.workflow_data.k2_seed), # Semilla del segundo Ksampler
            ("22", "steps", self.workflow_data.k2_steps), # Pasos del segundo Ksampler
            ("22", "cfg", self.workflow_data.k2_cfg), # CFG del segundo Ksampler
            ("22", "sampler_name", self.workflow_data.k2_sampler_name), # Sampler del segundo Ksampler
            ("22", "scheduler", self.workflow_data.k2_scheduler), # Scheduler del segundo Ksampler
            ("22", "denoise", self.workflow_data.k2_denoise), # Denoise del segundo Ksampler

            ("25", "text", client.built_prompts["detailer_positive_prompt"]), # Detailer Positivo
            ("26", "text", client.built_prompts["detailer_negative_prompt"]), # Detailer Negativo

            ("27", "model_name", self.workflow_data.detailer_bbox_model), # Modelo de BBox para Detailer

            ("28", "seed", self.workflow_data.detailer_seed), # Semilla del face detailer
            ("28", "steps", self.workflow_data.detailer_steps), # Pasos del face detailer
            ("28", "cfg", self.workflow_data.detailer_cfg), # CFG del face detailer
            ("28", "sampler_name", self.workflow_data.detailer_sampler_name), # Sampler del detailer
            ("28", "scheduler", self.workflow_data.detailer_scheduler), # Scheduler del detailer
            ("28", "denoise", self.workflow_data.detailer_denoise), # Denoise del detailer
            ("28", "wildcard", client.built_prompts["detailer_wildcard_prompt"]), # Detailer Wildcard
            ("28", "feather", self.workflow_data.detailer_feather), # Feather del detailer
            ("28", "bbox_threshold", self.workflow_data.detailer_bbox_threshold), # BBox Threshold del detailer
            ("28", "bbox_dilation", self.workflow_data.detailer_bbox_dilation), # BBox Dilation del detailer
            ("28", "bbox_crop_factor", self.workflow_data.detailer_bbox_crop_factor), # BBox Crop Factor del detailer
            ("28", "drop_size", self.workflow_data.detailer_drop_size), # Drop Size del detailer

            ("32", "mask_bbox_padding", self.workflow_data.hands_refiner_mask_bbox_padding), # Mask BBox Padding del Hand Refiner
            ("32", "mask_type", self.workflow_data.hands_refiner_mask_type), # Mask Type del Hand Refiner
            ("32", "mask_expand", self.workflow_data.hands_refiner_mask_expand), # Mask Expand del Hand Refiner
            ("32", "detect_thr", self.workflow_data.hands_refiner_detect_thr), # Detection Threshold del Hand Refiner
            ("32", "presence_thr", self.workflow_data.hands_refiner_presence_thr), # Presence Threshold del Hand Refiner

            ("33", "text", client.built_prompts["hands_positive_prompt"]), # Hand Refiner Prompt Positivo
            ("34", "text", client.built_prompts["hands_negative_prompt"]), # Hand Refiner Prompt Negativo
            
            ("35", "control_net_name", self.workflow_data.hands_refiner_controlnet_model), # Modelo de ControlNet para Hand Refiner
            
            ("36", "strength", self.workflow_data.hands_refiner_controlnet_weight), # Peso de ControlNet para Hand Refiner
            ("36", "start_percent", self.workflow_data.hands_refiner_controlnet_start), # Inicio de ControlNet para Hand Refiner
            ("36", "end_percent", self.workflow_data.hands_refiner_controlnet_end), # Fin de ControlNet para Hand Refiner

            ("37", "seed", self.workflow_data.hands_refiner_seed), # Semilla del KSampler de Hand Refiner
            ("37", "steps", self.workflow_data.hands_refiner_steps), # Pasos del KSampler de Hand Refiner
            ("37", "cfg", self.workflow_data.hands_refiner_cfg), # CFG del KSampler de Hand Refiner
            ("37", "sampler_name", self.workflow_data.hands_refiner_sampler_name), # Sampler del KSampler de Hand Refiner
            ("37", "scheduler", self.workflow_data.hands_refiner_scheduler), # Scheduler del KSampler de Hand Refiner
            ("37", "denoise", self.workflow_data.hands_refiner_denoise), # Denoise del KSampler de Hand Refiner

            ("40", "filename_prefix", self.donor_data.vrepro_id) # Prefijo de archivo de salida
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

        return changes
