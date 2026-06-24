import logging
from typing import Dict, Any, Literal

from backend.src.composition.composition import Composition
from backend.src.composition.physical_traits import PhysicalTraits
from backend.src.composition.style_traits import StyleTraits
from backend.src.composition.trait_data_loader import TraitDataLoader
from backend.src.utils import get_with_default
from ..utils.hair_classifier import HairClassifier

class CompositionBuilder:
    """
    Builds a coherent composition of traits for fullbody or portrait image generation.

    This class encapsulates the logic for combining physical and style traits
    into a complete composition, which then informs the image generation process.
    It acts as an intermediary between raw donor data and the structured
    composition required by the image generation request, allowing for
    future overrides or extensions to the composition logic.
    """

    def __init__(
        self,
        physical_traits: PhysicalTraits,
        style_traits: StyleTraits,
        logger: logging.Logger = None,
    ):
        """
        Initializes the CompositionBuilder with physical and style traits.

        Args:
            physical_traits (PhysicalTraits): The donor's physical characteristics.
            style_traits (StyleTraits): The selected clothing styles.
            logger (logging.Logger, optional): A logger instance for recording process information.
        """
        self.physical: PhysicalTraits = physical_traits
        self.style: StyleTraits = style_traits
        self.logger: logging.Logger = logger
        self.composer = Composition(physical_traits, style_traits, logger=logger)

    def build(self, generation_type: Literal["fullbody", "portrait"]) -> Dict[str, Any]:
        """
        Builds and returns the complete composition based on the generation type.

        This method delegates to the internal `Composition` object to create
        either a fullbody or portrait-specific composition.

        Args:
            generation_type (Literal["fullbody", "portrait"]): The type of generation to build the composition for.

        Returns:
            Dict[str, Any]: A dictionary representing the complete composition,
                            with keys such as 'outfit_fullbody', 'hairstyle', 'makeup', etc.
        """
        generation_type = generation_type.lower()

        if generation_type not in {"fullbody", "portrait"}:
            raise ValueError(f"Invalid generation_type: {generation_type}. Must be 'fullbody' or 'portrait'.")

        if generation_type == "fullbody":
            composition = self.composer.composition_fullbody()
        else:  # portrait
            composition = self.composer.composition_portrait()

        if self.logger is not None:
            self.logger.debug(f"Composition built: {list(composition.keys())}")
        return composition

    @staticmethod
    def create_physical_traits(project_data: Dict[str, str], logger: logging.Logger = None) -> PhysicalTraits:
        """
        Static helper method to create a PhysicalTraits object from raw project data.

        It extracts and classifies relevant physical attributes from the provided
        `project_data` dictionary, applying default values if necessary.

        Args:
            project_data (Dict[str, str]): A dictionary containing donor data, typically from a CSV row.
            logger (logging.Logger, optional): A logger instance for recording information or warnings.

        Returns:
            PhysicalTraits: An instance of PhysicalTraits populated with the donor's physical attributes.
        """
        return PhysicalTraits(
            age=get_with_default(project_data, "age", "25").strip(),
            eye_color=get_with_default(project_data, "eyeColor", "Brown").strip(),
            hair_color=get_with_default(project_data, "hairColor", "Dark brown").strip(),
            hair_type=HairClassifier.classify_type(get_with_default(project_data, "hairType", "Straight")),
            hair_length=HairClassifier.classify_length(get_with_default(project_data, "hairLength", "Long")),
            body_type=get_with_default(project_data, "bodyType", "Straight").strip(),
            body_complexion=get_with_default(project_data, "bodyComplexion", "Average build").strip(),
            bust_type=get_with_default(project_data, "bustType", "Proportional").strip(),
            thigh_type=get_with_default(project_data, "thighType", "Proportional").strip(),
            skin_tone=get_with_default(project_data, "skinTone", "White").strip(),
            special_characteristics=get_with_default(project_data, "specialCharacteristics", "").strip(),
        )

    @staticmethod
    def create_style_traits(
        clothing_style_1: str,
        clothing_style_2: str,
        trait_loader: 'TraitDataLoader',
        logger: logging.Logger = None
    ) -> StyleTraits:
        """
        Static helper method to create a StyleTraits object from one or two clothing styles.

        It validates the provided style names against the `trait_loader` and
        falls back to a default 'casual' style if the primary style is not found.

        Args:
            clothing_style_1 (str): The primary clothing style name.
            clothing_style_2 (str): An optional secondary clothing style name.
            trait_loader (TraitDataLoader): An instance of TraitDataLoader to validate style names.
            logger (logging.Logger): A logger instance for recording warnings.

        Returns:
            StyleTraits: An instance of StyleTraits containing the validated and selected styles.
        """
        styles = []
        style1_key = f"style_{clothing_style_1.lower()}"

        if style1_key in trait_loader.get_all_style_names():
            styles.append(style1_key)
        else:
            if logger is not None:
                logger.warning(f"Style '{clothing_style_1}' not found. Falling back to 'casual'.")
            styles.append("style_casual")

        if clothing_style_2:
            style2_key = f"style_{clothing_style_2.lower()}"
            if style2_key in trait_loader.get_all_style_names():
                styles.append(style2_key)
            else:
                if logger is not None:
                    logger.warning(f"Style '{clothing_style_2}' not found. Skipping secondary style.")

        return trait_loader.create_style_traits(styles)