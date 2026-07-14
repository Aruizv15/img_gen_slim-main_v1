from typing import List, Dict, Any

from src.config.settings import get_settings
from backend.src.generator.image_generator import ImageGenerator
from .base_request import BaseRequest
from .scene.portrait_scene_data import PortraitSceneData
from .workflow.portrait_workflow_data import PortraitWorkflowData

from src.utils import save_json_file

SETTINGS = get_settings()

class PortraitRequest(BaseRequest[PortraitSceneData, PortraitWorkflowData]):
    """
    A concrete implementation of a request to generate portrait images.

    This class specializes the `BaseRequest` to handle the specific requirements
    of generating portrait images. It defines how to assemble the positive
    prompt arguments, which workflow arguments to set, and how to modify the
    workflow structure based on the request's configuration.
    """
    def _get_positive_prompt_args(self) -> Dict[str, Any]:
        """Assembles the arguments for the positive prompt template.

        Returns:
            A dictionary containing all the dynamic values needed to format
            the portrait positive prompt.
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
            "skin_tone": self.donor_data.skin_tone,
            "special_characteristics": special_char_text,
            "outfit_type": self.appearance_data.outfit_type,
            "outfit_color": self.appearance_data.outfit_color,
            "hairstyle_type": self.appearance_data.hairstyle_type,
            "makeup_type": self.appearance_data.makeup_type,
            "expression": self.scene_data.expression,
            "background": self.scene_data.background,
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
            ("1", "ckpt_name", self.workflow_data.checkpoint), # Checkpoint Model

            ("2", "batch_size", self.workflow_data.batch_size), # Tamaño del lote

            ("3", "text", client.built_prompts["positive_prompt"]), # Prompt Positivo
            ("4", "text", client.built_prompts["negative_prompt"]), # Prompt Negativo

            ("5", "image", self.workflow_data.ref_image), # Nodo de carga de imagen principal (referencia)

            ("6", "preprocessor", self.workflow_data.controlnet_preprocessor), # Preprocesador de ControlNet
            ("6", "sd_version", self.workflow_data.controlnet_preprocessor_sd_version), # Versión de SD para Preprocesador de ControlNet

            ("7", "control_net_name", self.workflow_data.pose_controlnet_model), # Modelo de ControlNet de pose

            ("8", "strength", self.workflow_data.pose_controlnet_weight), # Peso de ControlNet de pose
            ("8", "start_percent", self.workflow_data.pose_controlnet_start), # Inicio de ControlNet de pose
            ("8", "end_percent", self.workflow_data.pose_controlnet_end), # Fin de ControlNet de pose

            ("9", "seed", self.workflow_data.k1_seed), # Semilla del primer Ksampler
            ("9", "steps", self.workflow_data.k1_steps), # Pasos del primer Ksampler
            ("9", "cfg", self.workflow_data.k1_cfg), # CFG del primer Ksampler
            ("9", "sampler_name", self.workflow_data.k1_sampler_name), # Sampler del primer Ksampler
            ("9", "scheduler", self.workflow_data.k1_scheduler), # Scheduler del primer Ksampler

            ("10", "lora_name", self.workflow_data.ipadapter_lora_name), # LoRA IPAdapter
            ("10", "strength_model", self.workflow_data.ipadapter_lora_strength_model), # Fuerza de modelo de LoRA
            ("10", "strength_clip", self.workflow_data.ipadapter_lora_strength_clip), # Fuerza de clip de LoRA

            ("11", "directory", self.workflow_data.ref_directory), # Directorio para el nodo 11 (Load Image)

            ("13", "clip_name", self.workflow_data.clip_vision_model), # Modelo de CLIP Vision

            ("14", "model_name", self.workflow_data.insightface_model_name), # Modelo de InsightFace

            ("15", "preset", self.workflow_data.faceid_loader_preset), # Preset de FaceID Loader
            ("15", "lora_strength", self.workflow_data.faceid_loader_lora_strength), # Fuerza de LoRA de FaceID Loader

            ("16", "weight", self.workflow_data.faceid_weight), # Peso de FaceID
            ("16", "weight_faceidv2", self.workflow_data.faceid_v2_weight), # Peso de FaceID v2
            ("16", "weight_type", self.workflow_data.faceid_weight_type), # Tipo de peso de FaceID
            ("16", "combine_embeds", self.workflow_data.faceid_combine_embeds), # Combinación de embeds de FaceID
            ("16", "start_at", self.workflow_data.faceid_start), # Inicio de FaceID
            ("16", "end_at", self.workflow_data.faceid_end), # Fin de FaceID

            ("17", "preset", self.workflow_data.plus_face_loader_preset), # Preset de Plus Face Loader

            ("18", "weight", self.workflow_data.plus_face_weight), # Peso de Plus Face
            ("18", "weight_type", self.workflow_data.plus_face_weight_type), # Tipo de peso de Plus Face
            ("18", "combine_embeds", self.workflow_data.plus_face_combine_embeds), # Combinación de embeds de Plus Face
            ("18", "start_at", self.workflow_data.plus_face_start), # Inicio de Plus Face
            ("18", "end_at", self.workflow_data.plus_face_end), # Fin de Plus Face

            ("19", "seed", self.workflow_data.k2_seed), # Semilla del segundo Ksampler
            ("19", "steps", self.workflow_data.k2_steps), # Pasos del segundo Ksampler
            ("19", "cfg", self.workflow_data.k2_cfg), # CFG del segundo Ksampler
            ("19", "sampler_name", self.workflow_data.k2_sampler_name), # Sampler del segundo Ksampler
            ("19", "scheduler", self.workflow_data.k2_scheduler), # Scheduler del segundo Ksampler
            ("19", "denoise", self.workflow_data.k2_denoise), # Denoise del segundo Ksampler

            ("22", "text", client.built_prompts["detailer_positive_prompt"]), # Detailer Positivo
            ("23", "text", client.built_prompts["detailer_negative_prompt"]), # Detailer Negativo

            ("24", "model_name", self.workflow_data.detailer_bbox_model), # Modelo de BBox para Detailer

            ("25", "seed", self.workflow_data.detailer_seed), # Semilla del face detailer
            ("25", "steps", self.workflow_data.detailer_steps), # Pasos del face detailer
            ("25", "cfg", self.workflow_data.detailer_cfg), # CFG del face detailer
            ("25", "sampler_name", self.workflow_data.detailer_sampler_name), # Sampler del detailer
            ("25", "scheduler", self.workflow_data.detailer_scheduler), # Scheduler del detailer
            ("25", "denoise", self.workflow_data.detailer_denoise), # Denoise del detailer
            ("25", "wildcard", client.built_prompts["detailer_wildcard_prompt"]), # Detailer Wildcard
            ("25", "feather", self.workflow_data.detailer_feather), # Feather del detailer
            ("25", "bbox_threshold", self.workflow_data.detailer_bbox_threshold), # BBox Threshold del detailer
            ("25", "bbox_dilation", self.workflow_data.detailer_bbox_dilation), # BBox Dilation del detailer
            ("25", "bbox_crop_factor", self.workflow_data.detailer_bbox_crop_factor), # BBox Crop Factor del detailer
            ("25", "drop_size", self.workflow_data.detailer_drop_size), # Drop Size del detailer

            ("27", "filename_prefix", self.donor_data.vrepro_id) # Prefijo de archivo de salida
        ]
        return workflow_args
    
    def _get_structural_changes(self):
        """
        Builds a dictionary of structural modifications to be applied to the ComfyUI workflow.

        Returns:
            A dictionary containing the keys 'remove' and 'reconnect':
            {
                "remove": List[str],
                "reconnect": List[tuple]
            }
        """
        changes = {
            "remove": [],
            "reconnect": []
        }

        if not self.workflow_data.use_reference_pose:
            # NOTA: se quito "28" de esta lista porque ese nodo (era un
            # "easy cleanGpuUsed" del paquete ComfyUI-Easy-Use, roto) ya
            # fue eliminado directamente del archivo portrait.json. Dejarlo
            # aqui causaria "Node '28' was not found in the workflow".
            changes["remove"].extend(["5", "6", "7", "8"])
            changes["reconnect"].extend([("3", 0, "9", "positive"), ("4", 0, "9", "negative"), ("2", 0, "9", "latent_image")])

        return changes
