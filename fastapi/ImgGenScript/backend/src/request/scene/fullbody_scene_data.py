from dataclasses import dataclass
from .scene_data import SceneData

@dataclass
class FullBodySceneData(SceneData):
    """
    Stores scene-specific data for a full-body image generation.

    This data class extends `SceneData` with attributes that are unique to
    full-body compositions.

    Args:
        pose (str): The full-body pose of the subject.
        expression (str): The facial expression of the subject.
        environment (str): The type of environment for the scene (e.g., 'env_indoor', 'env_outdoor').
        location (str): The environment or location where the scene takes place.
        lighting (str): The description of the lighting for the scene.
        light_temperature (str): The temperature of the light for the scene (e.g., 'light_temp_cool', 'light_temp_warm').
    """
    pose: str
    location: str
