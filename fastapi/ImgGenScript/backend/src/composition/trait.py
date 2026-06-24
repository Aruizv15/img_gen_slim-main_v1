from dataclasses import dataclass, field
from typing import List, Dict

@dataclass(frozen=True)
class Trait:
    """
    A single style trait (Color, Pose, Location, etc.) with its associated affinities.

    This dataclass represents an atomic piece of stylistic information that can be 
    used in the composition process. It is frozen, meaning its attributes cannot 
    be changed after initialization.

    Attributes:
        trait_type (str): The category this trait belongs to (e.g., "Outfit", "Lighting").
        value (str): The specific value of the trait (e.g., "Red Dress", "Soft Light").
        tags (Dict[str, List[str]]): A dictionary of tags organized by category.
        style_affinities (List[str]): A list of style names this trait is particularly 
            associated with or recommended for.
    """
    trait_type: str
    value: str
    tags: Dict[str, List[str]] = field(default_factory=dict)
    style_affinities: List[str] = field(default_factory=list)

    @property
    def all_tags(self) -> List[str]:
        """
        Returns all tags associated with the trait in a single, flat list.

        This property combines all values from the `tags` dictionary into one 
        unified list, regardless of their original category.

        Returns:
            List[str]: A list containing every tag value.
        """
        return [tag for tag_list in self.tags.values() for tag in tag_list]
    