from typing import Dict
from dataclasses import dataclass
from abc import ABC

@dataclass
class SceneData(ABC):
    """
    An abstract base class for all types of scene data.

    This class defines the common parameters that are shared across different
    scene types, such as expression and lighting. Subclasses should inherit
    from this class to add specific attributes for their context (e.g., pose,
    location, background).

    Args:
        expression (str): The facial expression of the subject.
        environment (str): The type of environment for the scene (e.g., 'env_indoor', 'env_outdoor').
        lighting (str): The description of the lighting for the scene.
        light_temperature (str): The temperature of the light for the scene (e.g., 'light_temp_cool', 'light_temp_warm').
    """
    expression: str
    environment: str
    lighting: str
    light_temperature: str

    def to_dict(self) -> Dict[str, str]:
        """
        Converts the instance's attributes to a dictionary.

        Returns:
            A dictionary representation of the SceneData instance.
        """
        return self.__dict__