from dataclasses import dataclass, field
from typing import List, Dict

from backend.src.composition.trait import Trait

@dataclass
class StyleDefinition:
    """
    Represents the complete definition of a single style.

    This data class acts as a container for all possible traits associated with a
    specific style (e.g., 'minimalist', 'bohemian'). It organizes these traits
    by their type, making them easily accessible.

    Attributes:
        name (str): The unique name of the style (e.g., 'casual').
        trait_options (Dict[str, List[Trait]]): A dictionary where keys are trait types (e.g., 'locations',
            'outfits_fullbody') and values are lists of `Trait` objects belonging to that type and style.
    """
    name: str
    trait_options: Dict[str, List[Trait]] = field(default_factory=dict)

    @property
    def summary(self) -> Dict[str, List[str]]:
        """
        Provides a summary of trait options by type, showing only their values.

        Returns:
            A dictionary where keys are trait types and values are lists of the
            string values of the traits, useful for debugging and inspection.
        """
        summary = {}
        for trait_type, traits in self.trait_options.items():
            summary[trait_type] = [t.value for t in traits]