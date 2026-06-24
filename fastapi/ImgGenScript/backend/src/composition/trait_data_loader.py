import json
import warnings
from typing import List, Dict, Any
from pathlib import Path

from backend.src.composition.style_definition import StyleDefinition
from backend.src.composition.trait import Trait 
from backend.src.composition.style_traits import StyleTraits 
from backend.src.utils.io import load_json_file
from backend.src.config.settings import get_settings, Settings

SETTINGS: Settings = get_settings()

class TraitDataLoader:
    """
    Loads, parses, and structures all trait data into `StyleDefinition` templates.

    This class is responsible for reading all `.json` files from a specified
    directory, parsing them into `Trait` objects, and then organizing these
    traits into `StyleDefinition` objects based on their style affinities.
    The final result is a collection of ready-to-use style templates.

    Attributes:
        styles (Dict[str, StyleDefinition]): A dictionary mapping style names
            (e.g., 'style_minimalist') to their fully constructed
            `StyleDefinition` objects.
    """
    def __init__(self, folder_path: str = SETTINGS.styles_dir):
        """
        Initializes the data loader and executes the full loading process.

        The initialization sequence loads JSON files, converts the data into 
        `Trait` objects, groups them by style affinity, and finally constructs 
        the `StyleDefinition` objects.

        Args:
            folder_path (str, optional): The absolute path to the directory 
                containing the JSON files with the trait definitions.
        """
        # Internal storage for processing
        self._traits_by_style: Dict[str, List[Trait]] = {}
        self.styles: Dict[str, StyleDefinition] = {}
        
        # Execution flow
        file_contents = self._load_json_files_from_folder(folder_path)
        self._load_and_group_traits(file_contents)
        self._build_style_templates()

    def _load_json_files_from_folder(self, folder_path: str) -> Dict[str, Any]:
        """
        Reads all .json files from the given folder.

        Returns:
            A dictionary mapping filenames to their parsed JSON content.
        """
        path = Path(folder_path)
        if not path.is_dir():
            raise FileNotFoundError(f"The folder path is not valid or does not exist: {folder_path}")
            
        file_contents: Dict[str, Any] = {}
        
        # Busca recursivamente archivos .json
        for file_path in path.glob('*.json'):
            if file_path.is_file():
                try:
                    content = load_json_file(str(file_path))
                    file_contents[file_path.name] = content
                except (json.JSONDecodeError, IOError) as e:
                    warnings.warn(f"Could not read or parse file {file_path.name}. Error: {e}")
                    
        return file_contents


    def _load_and_group_traits(self, file_contents: Dict[str, Any]) -> None:
        """
        Parses JSON content into Trait objects and groups them by style affinity.

        This method performs two main steps:
            1. It iterates through the content of each JSON file, creating `Trait` objects.
            2. It then groups these `Trait` objects into the `_traits_by_style` dictionary based on their `style_affinities`.
        """
        all_traits: List[Trait] = []
        
        # Paso 1: Cargar todos los Traits
        for filename, data in file_contents.items():
            if not filename.endswith('.json'):
                continue
            
            # Assumes the trait type is the only top-level key
            trait_type = next(iter(data.keys()))
            
            for item in data[trait_type]:
                trait = Trait( # Uso de la clase Trait
                    value=item.get('value', ''),
                    tags=item.get('tags', {}),
                    style_affinities=item.get('style', []),
                    trait_type=trait_type
                )
                all_traits.append(trait)
        
        # Step 2: Group by style
        for trait in all_traits:
            for style_name in trait.style_affinities:
                if style_name not in self._traits_by_style:
                    self._traits_by_style[style_name] = []
                self._traits_by_style[style_name].append(trait)

    def _build_style_templates(self) -> None:
        """
        Constructs the final `StyleDefinition` instances.

        This method iterates through the traits grouped by style and constructs
        a `StyleDefinition` object for each style, organizing the traits within it by their type.
        """
        for style_name, traits in self._traits_by_style.items():
            # Group the traits of this style by their type (color, pose, etc.)
            trait_options_by_type: Dict[str, List[Trait]] = {}
            for trait in traits:
                if trait.trait_type not in trait_options_by_type:
                    trait_options_by_type[trait.trait_type] = []
                trait_options_by_type[trait.trait_type].append(trait)
            
            # Create the StyleDefinition instance
            self.styles[style_name] = StyleDefinition( # Uso de la clase StyleDefinition
                name=style_name,
                trait_options=trait_options_by_type
            )
            
    # --- Métodos de Interfaz Pública ---

    def get_style_definition(self, style_name: str) -> StyleDefinition | None:
        """
        Retrieves a specific `StyleDefinition` template by name.

        Args:
            style_name: The name of the style to retrieve.

        Returns:
            The requested `StyleDefinition` object, or `None` if not found.
        """
        return self.styles.get(style_name)

    def get_all_style_names(self) -> List[str]:
        """
        Returns a list of all available style names.

        Returns:
            A list of strings, where each string is an identified style name.
        """
        return list(self.styles.keys())
    
    def create_style_traits(self, style_names: List[str]) -> StyleTraits:
        """
        Creates a `StyleTraits` instance by merging the requested styles.

        Args:
            style_names: A list of style names to be merged.

        Returns:
            A `StyleTraits` object containing the combined traits from the specified styles.
        """
        return StyleTraits(style_names, self.styles)