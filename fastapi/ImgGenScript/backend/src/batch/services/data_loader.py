import logging
from pathlib import Path
from typing import Dict, List, Optional

from backend.src.config.settings import Settings, get_settings
from backend.src.utils import (
    load_text_file,
    load_csv_data,
    find_project_dirs,
    compare_lists,
)
from backend.src.composition.trait_data_loader import TraitDataLoader

class DataLoader:
    """
    Handles the loading of all necessary input data for a batch generation process.

    This class centralizes data-loading operations, acting as a single source
    for various data types required by the orchestrator and processors. Its
    responsibilities include:
    - Loading donor information from a central CSV file.
    - Reading text-based prompt templates from the filesystem.
    - Discovering and validating project directories (e.g., 'OVODxxxxx').
    - Initializing the `TraitDataLoader` to load style and characteristic data.

    It is designed to separate data access from business logic, ensuring that
    other components receive data in a consistent and structured format.
    """

    def __init__(self, logger: logging.Logger = None, settings: Settings = None):
        """
        Initializes the DataLoader.

        Args:
            logger (logging.Logger, optional): A logger instance for recording
                loading activities and errors. Defaults to None.
            settings (Settings, optional): A configuration object. If not
                provided, it will be loaded via `get_settings()`. Defaults to None.
        """
        self.logger = logger
        self.settings = settings or get_settings()        

    def load_trait_data(self) -> TraitDataLoader:
        """
        Loads all trait data, including styles and physical characteristics.

        This method initializes and returns a `TraitDataLoader` instance, which
        is responsible for parsing and structuring all style-related information
        from the configuration files.

        Returns:
            TraitDataLoader: An instance fully loaded with all available traits.

        Raises:
            RuntimeError: If the trait data cannot be loaded, which is a
                critical failure for the batch process.
        """
        try:
            if self.logger is not None:
                self.logger.debug("Loading trait data (styles and characteristics)...")
            trait_loader = TraitDataLoader()
            if self.logger is not None:
                self.logger.debug(f"Traits loaded: {len(trait_loader.get_all_style_names())} styles available.")
            return trait_loader
        except Exception as e:
            if self.logger is not None:
                self.logger.critical(f"Critical error loading traits: {e}")
            raise RuntimeError(f"Could not load traits: {e}") from e

    def load_donor_csv(self) -> Dict[str, Dict[str, str]]:
        """
        Loads the donor information from the CSV file and maps it by `vreproID`.

        This method reads the main CSV file containing data for all donors and
        structures it into a dictionary for quick lookup by the project's unique ID.

        Returns:
            A dictionary where keys are `vreproID` strings and values are dictionaries representing each CSV row.
        """
        csv_path = Path(self.settings.csv_dir) / self.settings.donor_info_file
        if self.logger is not None:
            self.logger.debug(f"Loading donor CSV from: {csv_path}")

        if not csv_path.exists():
            if self.logger is not None:
                self.logger.critical(f"CSV file not found: {csv_path}")
            raise FileNotFoundError(f"CSV not found: {csv_path}")

        try:
            csv_data = load_csv_data(csv_path, self.logger)
            donor_map = {row["vreproID"]: row for row in csv_data}
            if self.logger is not None:
                self.logger.debug(f"CSV loaded: {len(donor_map)} donors found.")
            return donor_map
        except Exception as e:
            if self.logger is not None:
                self.logger.critical(f"Error reading CSV: {e}")
            raise

    def load_prompt_templates(self) -> Dict[str, str]:
        """
        Loads all required prompt templates from their respective text files.

        Returns:
            A dictionary where keys are the prompt's purpose (e.g., "fullbody_positive", "negative") and values are the file contents as strings.
        """
        prompts_dir = Path(self.settings.prompts_dir)

        if self.logger is not None:
            self.logger.debug("Loading prompt templates...")

        templates = {
            "fullbody_positive": self.settings.fullbody_prompt_template,
            "portrait_positive": self.settings.portrait_prompt_template,
            "negative": self.settings.negative_prompt_template,
            "detailer_positive": self.settings.detailer_positive_prompt_template,
            "detailer_negative": self.settings.detailer_negative_prompt_template,
            "detailer_wildcard": self.settings.detailer_wildcard_prompt_template,
            "hands_positive": self.settings.hands_positive_prompt_template,
            "hands_negative": self.settings.hands_negative_prompt_template,
        }

        loaded_prompts = {}
        for key, filename in templates.items():
            file_path = prompts_dir / filename
            try:
                content = load_text_file(file_path, self.logger)
                loaded_prompts[key] = content
                if self.logger is not None:
                    self.logger.debug(f"Prompt '{key}' loaded from {file_path}")
            except FileNotFoundError:
                if self.logger is not None:
                    self.logger.warning(f"Prompt file not found: {file_path}. Using empty string.")
                loaded_prompts[key] = ""
            except Exception as e:
                if self.logger is not None:
                    self.logger.error(f"Error loading prompt {key}: {e}")
                loaded_prompts[key] = ""

        return loaded_prompts

    def load_project_dirs(
        self,
        donor_list: Optional[List[str]] = None
    ) -> List[str]:
        """
        Finds all project directories (e.g., 'OVODxxxxx') and optionally filters them.

        This method scans the base images directory for all valid project folders.
        If a `donor_list` is provided, it filters the results to include only
        those specified, raising an error if any are not found.

        Args:
            donor_list (List[str], optional): A list of specific project IDs to process. If None, all found projects are returned.

        Returns:
            A list of full string paths to the project directories that should be processed.
        """
        if self.logger is not None:
            self.logger.debug("Searching for project directories (OVODxxxxx)...")
        all_dirs = find_project_dirs(self.settings.images_dir, self.logger)

        if not all_dirs:
            if self.logger is not None:
                self.logger.critical(f"No OVODxxxxx directories found in {self.settings.images_dir}")
            raise RuntimeError("No projects found to process.")

        if not donor_list:
            if self.logger is not None:
                self.logger.debug(f"{len(all_dirs)} projects found. Processing all.")
            return all_dirs

        requested = [str(Path(self.settings.images_dir) / d) for d in donor_list]
        valid_dirs, missing = compare_lists(requested, all_dirs)

        if missing:
            if self.logger is not None:
                self.logger.critical(f"Projects not found: {missing}")
            raise RuntimeError(f"Donors not found: {missing}")

        if self.logger is not None:
            self.logger.debug(f"{len(valid_dirs)} requested projects found and ready.")
        return valid_dirs

    def load_all(
        self,
        generation_type: str,
        donor_list: Optional[List[str]] = None
    ) -> Dict:
        """
        Loads all data required for a batch run in a single call.

        This is a convenience method that orchestrates the loading of traits,
        donor data, prompts, and project directories.

        Args:
            generation_type (str): The type of generation ('fullbody' or 'portrait') to load specific prompts for.
            donor_list (List[str], optional): An optional list of donor IDs to filter the project directories.

        Returns:
            A dictionary containing all loaded data, with keys: 'trait_loader', 'donor_map', 'prompts', and 'project_dirs'.
        """
        if self.logger is not None:
            self.logger.debug(f"Starting full data load for {generation_type}...")

        return {
            "trait_loader": self.load_trait_data(),
            "donor_map": self.load_donor_csv(),
            "prompts": self.load_prompt_templates(generation_type),
            "project_dirs": self.load_project_dirs(donor_list),
        }