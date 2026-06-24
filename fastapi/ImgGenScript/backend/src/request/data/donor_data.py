from typing import Dict
from dataclasses import dataclass

@dataclass
class DonorData:
    """
    Encapsulates all information related to a specific donor.

    This data class holds the core physical characteristics and identification
    details for a single subject (donor).

    Args:
        vrepro_id (str): The donor's unique identifier, used as a file prefix.
        age (str): The donor's age.
        eye_color (str): The color of the donor's eyes.
        hair_color (str): The color of the donor's hair.
        hair_type (str): The texture of the donor's hair (e.g., 'Straight', 'Wavy').
        hair_length (str): The length of the donor's hair (e.g., 'Short', 'Long').
        body_type (str): The donor's body shape or type.
        body_complexion (str): The overall build of the donor (e.g., 'Slim', 'Curvy').
        bust_type (str): The donor's bust size.
        thigh_type (str): The donor's thigh size.
        skin_tone (str): The donor's skin tone.
        special_characteristics (str): Any unique physical markings or features (e.g., 'freckles', 'moles').
    """
    vrepro_id: str
    age: str
    eye_color: str
    hair_color: str
    hair_type: str
    hair_length: str
    body_type: str
    body_complexion: str
    bust_type: str
    thigh_type: str
    skin_tone: str
    special_characteristics: str

    def to_dict(self) -> Dict[str, str]:
        """
        Converts the instance's attributes to a dictionary.

        Returns:
            A dictionary representation of the DonorData instance.
        """
        return self.__dict__