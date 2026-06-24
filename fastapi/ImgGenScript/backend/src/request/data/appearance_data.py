from typing import Dict
from dataclasses import dataclass

@dataclass
class AppearanceData:
    """
    Stores the appearance parameters for an image generation.

    This data class holds the stylistic choices for a specific image, such as
    the outfit and hairstyle, which are typically determined by the composition
    process.

    Args:
        outfit_type (str): The type of outfit to be worn.
        outfit_color (str): The color of the outfit.
        hairstyle_type (str): The hairstyle for the image.
        makeup_type (str): The type of makeup to be applied.
    """
    outfit_type: str
    outfit_color: str
    hairstyle_type: str
    makeup_type: str

    def to_dict(self) -> Dict[str, str]:
        """
        Converts the instance's attributes to a dictionary.

        Returns:
            A dictionary representation of the AppearanceData instance.
        """
        return self.__dict__