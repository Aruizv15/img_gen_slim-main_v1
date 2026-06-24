import random
import logging
from typing import Dict, List, Any, Set, Optional

from backend.src.composition.trait import Trait
from backend.src.composition.physical_traits import PhysicalTraits
from backend.src.composition.style_traits import StyleTraits

class Composition:
    """
    Orchestrates the creation of a coherent set of traits for image generation.

    This class takes physical traits of a subject and a set of stylistic options
    and combines them to produce a consistent and logical "composition". It ensures
    that choices like outfits, hairstyles, and lighting are compatible with each
    other and with the subject's physical attributes by applying a series of
    sequential filters based on tags.

    Attributes:
        physical (PhysicalTraits): An object containing the physical attributes
            of the subject (e.g., hair type, hair length).
        style_options (StyleTraits): An object providing access to all available
            stylistic traits (e.g., outfits, locations, poses) based on the
            selected styles.
        logger (Optional[logging.Logger]): A logger instance for logging warnings
            and other information.
    """
    def __init__(
            self,
            physical_traits: PhysicalTraits,
            style_traits: StyleTraits,
            logger: Optional[logging.Logger] = None
        ):
        """
        Initializes the Composition orchestrator.

        Args:
            physical_traits (PhysicalTraits): The object containing the base, 
                unchangeable physical attributes of the subject.
            style_traits (StyleTraits): The object containing the merged, de-duplicated 
                pool of stylistic options available for selection.
            logger (Optional[logging.Logger], optional): A logging instance for 
                tracking the composition selection process. Defaults to None.
        """
        self.physical: PhysicalTraits = physical_traits
        self.style_options: StyleTraits = style_traits
        self.logger: logging.Logger = logger

    def _filter_traits(
        self,
        trait_type: str,
        tag_requirements: Dict[str, Set[str]],
        match_all: bool = True
    ) -> List[Trait]:
        """
        Filters traits of a specific type based on tag requirements.

        Args:
            trait_type (str): The category of traits to filter (e.g., 'outfits_fullbody',
                'locations').
            tag_requirements Dict[str, Set[str]]: A dictionary where keys are tag categories (e.g.,
                'temperature') and values are sets of required tag values (e.g.,
                {'temp_hot'}). A trait must have at least one of the required tags
                for a given category.
            match_all (bool): If True, a trait must satisfy the requirements for all
                tag categories. If False, it must satisfy at least one.

        Returns:
            A list of `Trait` objects that meet the specified criteria.
        """
        trait_options = self.style_options[trait_type]
        coherent_options = []

        for trait in trait_options:
            conditions_met = []
            for category, required_tags in tag_requirements.items():
                trait_tags = set(trait.tags.get(category, []))
                conditions_met.append(not required_tags or bool(required_tags.intersection(trait_tags)))

            if (match_all and all(conditions_met)) or (not match_all and any(conditions_met)):
                coherent_options.append(trait)

        return coherent_options

    def _select_coherent_trait(
        self,
        trait_type: str,
        tag_requirements: Dict[str, Set[str]],
        fallback_warning: str
    ) -> Optional[Trait]:
        """
        Filters traits and randomly selects one, with a fallback mechanism.

        This method first attempts to find traits that match the given `tag_requirements`.
        If successful, it randomly selects one from the filtered list. If no traits
        match, it logs a warning and randomly selects one from the original,
        unfiltered list of options for that trait type.

        Args:
            trait_type (str): The category of trait to select from.
            tag_requirements (Dict[str, Set[str]]): The tag requirements used for filtering.
            fallback_warning (str): The warning message to log if no coherent trait is found.

        Returns:
            The selected `Trait` object, or `None` if no options are available at all.
        """
        options = self.style_options[trait_type]
        if not options:
            raise ValueError(f"No '{trait_type}' options available.")

        coherent_options = self._filter_traits(trait_type, tag_requirements)

        if not coherent_options:
            if self.logger:
                self.logger.warning(fallback_warning)
            return random.choice(options)
        
        return random.choice(coherent_options)

    def _compose_base(self, choices: Dict[str, Trait], outfit: Trait, env_tags: Set[str]):
        """
        Applies common composition logic for shared traits.

        This helper method populates the `choices` dictionary with coherent selections
        for outfit color, makeup, hairstyle, expression, and lighting.

        Args:
            choices (Dict[str, Trait]): A dictionary to be populated with the selected `Trait` objects.
            outfit (Trait): The primary `Trait` (outfit) to which other traits should be coherent.
            env_tags (Set[str]): A set of environment tags (e.g., 'env_indoor') derived from the
                location or background, used for selecting coherent lighting.
        """
        # --- Outfit Colors (Coherencia con Outfit) ---
        choices['outfit_color'] = self._select_coherent_trait(
            trait_type="outfit_colors",
            tag_requirements={
                "color_clarity": set(outfit.tags.get("color_clarity", [])),
                "color_saturation": set(outfit.tags.get("color_saturation", [])),
                "color_hue": set(outfit.tags.get("color_hue", [])),
                "color_family": set(outfit.tags.get("color_family", [])),
            },
            fallback_warning="No coherent colors found for the outfit. Choosing one at random."
        )

        # --- Makeup (Coherencia con Outfit) ---
        choices['makeup'] = self._select_coherent_trait(
            trait_type="makeups",
            tag_requirements={"makeup_intensity": set(outfit.tags.get("makeup_intensity", []))},
            fallback_warning="No coherent makeups found for the outfit. Choosing one at random."
        )

        # --- Hairstyles (Coherencia Física) ---
        choices['hairstyle'] = self._select_coherent_trait(
            trait_type="hairstyles",
            tag_requirements={
                "hair_type": {f"hair_type_{self.physical.hair_type.strip().lower()}"},
                "hair_length": {f"hair_length_{self.physical.hair_length.strip().lower()}"}
            },
            fallback_warning="No coherent hairstyles found for the physical traits. Choosing one at random."
        )

        # --- Expressions (Aleatorio) ---
        expression_options = self.style_options['expressions']
        if not expression_options:
            raise ValueError("No 'expressions' options available.")
        choices['expression'] = random.choice(expression_options)

        # --- Lighting (Coherencia de Ambiente) ---
        choices['lighting'] = self._select_coherent_trait(
            trait_type="lightings",
            tag_requirements={"environment": env_tags},
            fallback_warning="No coherent lighting found for the environment. Choosing one at random."
        )

    def composition_fullbody(self) -> Dict[str, Any]:
        """
        Generates a coherent composition for a full-body image.

        This method follows a sequence to build a logical set of traits:
            1. Randomly select a 'location'.
            2. Select a coherent 'outfit' based on the location's tags.
            3. Compose base traits (color, makeup, hairstyle) coherent with the outfit.
            4. Select a coherent 'pose' based on the chosen expression's emotion tag.
            5. Return the final composition as a dictionary of trait values.

        Returns:
            A dictionary mapping trait types to their selected string values,
            including the initial physical traits.
        """
        choices: Dict[str, Trait] = {}
        
        # --- 1. Location ---
        location_options = self.style_options['locations']
        if not location_options:
            raise ValueError("No 'locations' options available.")
        choices['location'] = location = random.choice(location_options)
        temp_tags = set(location.tags.get("temperature", []))
        env_tags = set(location.tags.get("environment", []))

        # --- 2. Outfit Fullbody ---
        choices['outfit_fullbody'] = outfit = self._select_coherent_trait(
            trait_type="outfits_fullbody",
            tag_requirements={"temperature": temp_tags, "environment": env_tags},
            fallback_warning="No coherent outfits found for the location. Choosing one at random."
        )

        # --- 3. Base Composition ---
        self._compose_base(choices, outfit, env_tags)

        # --- 4. Poses (Fullbody Specific) ---
        emotion_tag = set(choices['expression'].tags.get("emotion", []))
        if emotion_tag:
            choices['pose'] = self._select_coherent_trait(
                trait_type="poses",
                tag_requirements={"emotion": emotion_tag},
                fallback_warning="No coherent poses found for the emotion. Choosing one at random."
            )
        else:
            pose_options = self.style_options['poses']
            if not pose_options:
                raise ValueError("No 'poses' options available.")
            choices['pose'] = random.choice(pose_options)

        # --- 5. Final Return ---
        composition = self.physical.to_dict().copy()
        composition.update({k: v.value for k, v in choices.items()})
        
        composition['environment'] = next(iter(env_tags), None)
        light_temp_tags = choices.get('lighting').tags.get('light_temperature', set())
        composition['light_temperature'] = next(iter(light_temp_tags), None)
        
        return composition

    def composition_portrait(self) -> Dict[str, Any]:
        """
        Generates a coherent composition for a portrait image.

        This method follows a sequence to build a logical set of traits:
            1. Randomly select a 'background'.
            2. Select a coherent 'outfit' based on the background's tags.
            3. Compose base traits (color, makeup, hairstyle) coherent with the outfit.
            4. Return the final composition as a dictionary of trait values.

        Returns:
            A dictionary mapping trait types to their selected string values,
            including the initial physical traits.
        """
        choices: Dict[str, Trait] = {}
        
        # --- 1. Background ---
        background_options = self.style_options['backgrounds']
        if not background_options:
            raise ValueError("No 'backgrounds' options available.")
        choices['background'] = background = random.choice(background_options)
        temp_tags = set(background.tags.get("temperature", []))
        env_tags = set(background.tags.get("environment", []))

        # --- 2. Outfit Portrait ---
        choices['outfit_portrait'] = outfit = self._select_coherent_trait(
            trait_type="outfits_portrait",
            tag_requirements={"temperature": temp_tags, "environment": env_tags},
            fallback_warning="No coherent outfits found for the background. Choosing one at random."
        )

        # --- 3. Base Composition ---
        self._compose_base(choices, outfit, env_tags)

        # --- 4. Final Return ---
        composition = self.physical.to_dict().copy()
        composition.update({k: v.value for k, v in choices.items()})

        composition['environment'] = next(iter(env_tags), None)
        light_temp_tags = choices.get('lighting').tags.get('light_temperature', set())
        composition['light_temperature'] = next(iter(light_temp_tags), None)
        
        return composition