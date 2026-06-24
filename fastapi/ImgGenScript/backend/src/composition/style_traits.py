from typing import List, Dict

from backend.src.composition.trait import Trait
from backend.src.composition.style_definition import StyleDefinition

class StyleTraits:
    """
    Manages and merges trait options from multiple `StyleDefinition` objects.

    This class takes a list of style names and their corresponding `StyleDefinition`
    data to create a unified collection of all available traits. It is responsible
    for combining the traits from all specified styles and de-duplicating them
    to provide a final "master list" of options for the composition process.

    Attributes:
        style_names (List[str]): A list of the names of the styles being merged.
        styles (List[StyleDefinition]): A list of the `StyleDefinition` objects corresponding to the style names.
        master_trait_options: A dictionary containing the merged and de-duplicated
            trait options, organized by trait type.
    """
    def __init__(
            self,
            style_names: List[str],
            styles_data: Dict[str, StyleDefinition]
        ):
        """
        Initializes the StyleTraits manager by selecting and merging styles.

        Args:
            style_names (List[str]): A list of style names whose traits should be merged.
            styles_data (Dict[str, StyleDefinition]): A dictionary mapping all available 
                style names to their respective `StyleDefinition` objects. Only styles 
                whose names are in `style_names` will be selected.
        """
        self.style_names = style_names
        self.styles: List[StyleDefinition] = [
            styles_data[name] for name in style_names if name in styles_data
        ]
        self.master_trait_options: Dict[str, List[Trait]] = self._merge_styles()

    def _merge_styles(self) -> Dict[str, List[Trait]]:
        """
        Merges trait options from all combined styles.

        This method iterates through all the `StyleDefinition` objects and combines
        their traits. De-duplication is performed based on the trait's value (`Trait.value`)
        to ensure that each unique trait appears only once in the final list for its type.

        Returns:
            A dictionary where keys are trait types and values are the final,
            de-duplicated lists of `Trait` objects.
        """
        # Estructura temporal: {tipo_rasgo: {valor_rasgo: Trait_instance}}
        merged_options: Dict[str, Dict[str, Trait]] = {}
        
        for style in self.styles:
            for trait_type, traits in style.trait_options.items():
                if trait_type not in merged_options:
                    merged_options[trait_type] = {}
                
                for trait in traits:
                    merged_options[trait_type][trait.value] = trait
                    
        final_options = {
            trait_type: list(trait_map.values())
            for trait_type, trait_map in merged_options.items()
        }
        return final_options
    
    def get_options(self) -> Dict[str, List[Trait]]:
        """
        Returns all combined trait options.

        Returns:
            The master dictionary of merged trait options.
        """
        return self.master_trait_options

    def __getitem__(self, key: str) -> List[Trait]:
        """
        Allows dictionary-style access to trait options.
        """
        return self.master_trait_options.get(key, [])