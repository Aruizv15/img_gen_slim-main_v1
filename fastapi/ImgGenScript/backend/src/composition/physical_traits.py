from dataclasses import dataclass
from typing import Dict

@dataclass
class PhysicalTraits:
    """
    Encapsulates the core physical attributes of a subject.

    This class serves as a data container for the fundamental physical
    characteristics of a person, such as age, hair, and body type. These
    attributes are used as the base for generating a coherent composition.

    Attributes:
        age (str): The subject's age.
        eye_color (str): The color of the subject's eyes.
        skin_tone (str): The subject's skin tone.
        hair_color (str): The color of the subject's hair.
        hair_type (str): The texture of the subject's hair (e.g., 'straight', 'wavy').
        hair_length (str): The length of the subject's hair (e.g., 'short', 'long').
        body_type (str): The subject's body shape or type.
        body_complexion (str): The overall build of the subject (e.g., 'slim', 'curvy').
        bust_type (str): The subject's bust size.
        thigh_type (str): The subject's thigh size.
        special_characteristics (str): Any unique physical markings or features (e.g., 'freckles', 'moles').
    """
    age: str
    eye_color: str
    skin_tone: str
    hair_color: str
    hair_type: str
    hair_length: str
    body_type: str
    body_complexion: str
    bust_type: str
    thigh_type: str
    special_characteristics: str

    def to_dict(self) -> Dict[str, str]:
        """
        Converts the instance's attributes to a dictionary.

        Returns:
            A dictionary representation of the PhysicalTraits instance.
        """
        return self.__dict__