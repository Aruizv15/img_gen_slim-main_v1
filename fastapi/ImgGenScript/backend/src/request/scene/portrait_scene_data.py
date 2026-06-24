from dataclasses import dataclass
from .scene_data import SceneData

@dataclass
class PortraitSceneData(SceneData):
    """
    Stores scene-specific data for a portrait image generation.

    This data class extends `SceneData` with attributes that are unique to
    portrait compositions.

    Args:
        expression (str): The facial expression of the subject in the portrait.
        environment (str): The type of environment for the scene (e.g., 'env_indoor', 'env_outdoor').
        background (str): The background behind the subject in the portrait.
        lighting (str): The description of the lighting for the portrait.
        light_temperature (str): The temperature of the light for the scene (e.g., 'light_temp_cool', 'light_temp_warm').
    """
    background: str