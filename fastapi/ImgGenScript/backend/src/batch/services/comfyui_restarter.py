import os
import time
import logging

from dotenv import load_dotenv

from backend.src.config.settings import Settings, get_settings
from backend.src.clients.fastapi_client import FastAPIClient

load_dotenv()

class ComfyUIRestarter:
    """
    Manages the automatic restart of the ComfyUI service.

    This class encapsulates the logic for restarting ComfyUI after a configured
    number of generation runs. It handles:
    - Checking if a restart is necessary based on a run counter.
    - Sending an authorized restart command to the backend API.
    - Polling the API's health check endpoint to confirm it is back online.
    - Managing timeouts to prevent indefinite waiting.
    """
    def __init__(
            self,
            restart_token: str = None,
            logger: logging.Logger = None         
        ):
        """
        Initializes the ComfyUIRestarter.

        Args:
            restart_token (str, optional): The secret token required to authorize the restart action. If not provided, it's read from the `RESTART_TOKEN` environment variable.
            logger (logging.Logger, optional): A logger instance for recording restart events and errors.
        """
        self.settings: Settings = get_settings()
        self.restart_token: str = restart_token or os.getenv("RESTART_TOKEN")
        self.logger = logger
        self.client: FastAPIClient = FastAPIClient(self.settings.fastapi_server_address,logger=self.logger)
        
        
    def should_restart(self, total_runs: int) -> bool:
        """
        Determines if a ComfyUI restart is required based on the run count.

        Args:
            total_runs (int): The total number of generation runs completed so far.

        Returns:
            bool: True if the number of runs has reached the configured threshold (`max_runs`), otherwise False.
        """
        if self.settings.max_runs <= 0:
            return False
        if total_runs <= 0:
            return False
        return total_runs % self.settings.max_runs == 0

    def restart(self) -> bool:
        """
        Executes the full ComfyUI restart sequence.

        This method orchestrates the process:
        1. Sends the restart command to the backend API.
        2. Waits for the API to become healthy again by polling its health check endpoint.
        3. Applies a configured cooldown period after a successful restart.

        Returns:
            bool: True if the restart was successful and the API is responsive, otherwise False.
        """
        if self.logger is not None:
            self.logger.info(
                f"Max runs ({self.settings.max_runs}) reached. "
                "Initiating ComfyUI restart..."
            )

        # 1. Send restart command
        if not self.client.restart_comfyui(token=self.restart_token, verbose=False):
            if self.logger is not None:
                self.logger.error("Failed to send restart command to FastAPI.")
            return False

        if self.logger is not None:
            self.logger.info("Restart command sent. Waiting for FastAPI to come back online...")

        # 2. Wait for health check
        start_time = time.time()
        deadline = start_time + self.settings.restart_timeout

        while time.time() < deadline:
            if self.client.health_check():
                elapsed = int(time.time() - start_time)
                if self.logger is not None:
                    self.logger.info(f"FastAPI is back online after {elapsed} seconds.")
                time.sleep(self.settings.restart_cooldown)
                return True
            time.sleep(5)

        # 3. Handle timeout
        if self.logger is not None:
            self.logger.warning(
                f"Timeout: FastAPI did not respond after {self.settings.restart_timeout}s "
                "post-restart."
            )
        return False
    
    def check_and_restart(self, total_runs: int) -> bool:
        """
        Checks if a restart is needed and, if so, performs it.

        Args:
            total_runs (int): The current total number of generation runs.

        Returns:
            bool: True if no restart was needed or if the restart was successful. False if a required restart failed.
        """
        if not self.should_restart(total_runs):
            return True

        return self.restart()