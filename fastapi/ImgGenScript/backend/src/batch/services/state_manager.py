import logging
from pathlib import Path
from typing import Dict, Any

from backend.src.utils import load_json_file, save_json_file

class StateManager:
    """
    Manages the state of the batch generation process.

    This class is responsible for reading from and writing to a JSON state file,
    which tracks the progress and metrics of the batch runs. It handles:
    - Persisting the last processed project to allow for resumption.
    - Tracking global metrics like total, successful, and failed runs.
    - Providing a resilient interface that returns a default state in case of
      file errors, preventing crashes.
    """
    def __init__(self, state_file: Path, logger: logging.Logger = None):
        """
        Initializes the StateManager.

        Args:
            state_file (Path): The file path to the JSON file where the state is stored.
            logger (logging.Logger): A logger instance for recording state management activities.
        """
        self.state_file = state_file
        self.logger = logger
        self.default_state: Dict[str, Any] = {
            "fullbody": None,
            "portrait": None,
            "total_runs": 0,
            "successful_projects": 0,
            "failed_projects": 0
        }

    def read(self) -> dict:
        """
        Reads the current state from the JSON file.

        If the file does not exist or an error occurs during reading (e.g.,
        invalid JSON), it returns a default state to ensure the application
        can continue.

        Returns:
            A dictionary representing the current state.
        """
        if not self.state_file.exists():
            return self.default_state.copy()
        try:
            state = load_json_file(str(self.state_file), self.logger)
            return {**self.default_state, **state}
        except Exception as e:
            if self.logger is not None:
                self.logger.warning(f"Could not read state file, using default state. Error: {e}")
            return self.default_state.copy()

    def write(self, state: dict):
        """
        Writes the given state dictionary to the JSON file.

        Args:
            state (dict): The state dictionary to persist.
        """
        try:
            save_json_file(self.state_file, state, logger=self.logger)
        except Exception as e:
            if self.logger is not None:
                self.logger.error(f"Error saving state: {e}")

    def update_current(self, generation_type: str, donor_id: str):
        """
        Updates the state to mark a project as the currently processing one.

        Args:
            generation_type (str): The type of generation ('fullbody' or 'portrait').
            donor_id (str): The ID of the project (donor) being processed.
        """
        state = self.read()
        state[generation_type] = donor_id
        self.write(state)

    def clear_current(self, generation_type: str):
        """
        Clears the currently processing project from the state.

        This is typically called after a full cycle is completed.

        Args:
            generation_type (str): The type of generation ('fullbody' or 'portrait') to clear.
        """
        state = self.read()
        state[generation_type] = None
        self.write(state)
    
    def get_current(self, generation_type: str):
        """
        Gets the ID of the currently processing project for a given generation type.

        Args:
            generation_type (str): The type of generation ('fullbody' or 'portrait').

        Returns:
            The project ID (str) or None if no project is being processed.
        """
        state = self.read()
        return state.get(generation_type)

    def get_total_runs(self) -> int:
        """
        Gets the total number of generation runs performed.

        Returns:
            An integer representing the total run count.
        """
        return self.read().get("total_runs", 0)