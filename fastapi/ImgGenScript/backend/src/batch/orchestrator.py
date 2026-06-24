import time
import logging
import asyncio
from pathlib import Path
from typing import List, Optional, Literal

from backend.src.batch.services.state_manager import StateManager
from backend.src.batch.services.comfyui_restarter import ComfyUIRestarter
from backend.src.batch.services.data_loader import DataLoader
from backend.src.batch.processors.processor import ProjectProcessor
from backend.src.logger.logger import get_generation_logger
from backend.src.config.settings import get_settings

class BatchOrchestrator:
    """
    Orchestrates the batch image generation process for a specific type.

    This class manages the entire lifecycle of a batch generation task, such as
    'fullbody' or 'portrait'. It handles high-level control flow, including:
    - Managing generation cycles and project iteration.
    - Resuming from the last processed project to handle interruptions.
    - Tracking success and failure metrics via a state manager.
    - Triggering automatic ComfyUI restarts to manage memory.
    - Delegating data loading, processing, and state management to specialized
      services.
    """
    def __init__(
            self,
            generation_type: Literal["fullbody", "portrait"],
        ):
        """
        Initializes the BatchOrchestrator for a specific generation type.

        Args:
            generation_type (Literal["fullbody", "portrait"]): The type of
                generation task to orchestrate (e.g., 'fullbody').
        """
        self.generation_type = generation_type
        self.settings = get_settings()

        # Type-specific logger
        self.logger = get_generation_logger()

        # Injected services
        self.state_manager = StateManager(Path(self.settings.log_dir) / "batch_state.json", self.logger)
        self.restarter = ComfyUIRestarter(logger=self.logger)
        self.data_loader = DataLoader(self.logger, self.settings)

    async def run(
            self,
            max_cycles: int = -1,
            donor_list: List[str] = None,
            use_pose_override: bool = False,
            use_hands_refiner_override: bool = False,
            use_amateur_effect_override: bool = False
        ) -> None:
        """
        Executes the main batch generation loop.

        This method initializes all necessary data (traits, CSV, prompts),
        determines the list of projects to process, and then enters a loop
        to generate images for each project. The loop can run a fixed number
        of times or indefinitely.

        Args:
            max_cycles (int): The maximum number of full generation cycles to complete.
                A cycle processes all specified donors once. Defaults to -1 (infinite).
            donor_list (List[str], optional): A list of specific donor IDs to process.
                If empty, all found donor directories will be processed.
            use_pose_override (bool): Overrides the default 'use_pose' setting.
            use_hands_refiner_override (bool): Overrides the default 'use_hands_refiner' setting.
            use_amateur_effect_override (bool): Overrides the default 'use_amateur_effect' setting.
        """

        donor_list = donor_list or []
        # --- 1. Load Data ---
        trait_loader = self.data_loader.load_trait_data()
        csv_data_map = self.data_loader.load_donor_csv()
        prompts = self.data_loader.load_prompt_templates()
        project_dirs = self.data_loader.load_project_dirs(donor_list)

        if not project_dirs:
            self.logger.critical("No project directories found. Exiting.")
            return

        # --- 2. Processor ---
        project_processor = ProjectProcessor(
            trait_loader=trait_loader,
            prompts=prompts,
            logger=self.logger,
        )

        # --- 3. Main Loop ---
        cycle_count = 0
        while max_cycles == -1 or cycle_count < max_cycles:
            cycle_count += 1
            self.logger.info(f"--- Starting Cycle {cycle_count} ({self.generation_type}) ---")

            start_index = self._get_resume_index(project_dirs)

            for i in range(start_index, len(project_dirs)):
                project_dir_path = Path(project_dirs[i])
                project_name = project_dir_path.name

                self._update_current_project(project_name)

                project_data = csv_data_map.get(project_name)
                if not project_data:
                    self.logger.warning(f"No CSV data for {project_name}. Skipping.")
                    continue

                success = await self._process_project_with_retries(
                    project_processor,
                    project_data,
                    project_dir_path,
                    use_pose_override,
                    use_hands_refiner_override,
                    use_amateur_effect_override
                )

                self._record_project_result(success=success)

            self._clear_current_project()
            self.logger.info(f"--- Cycle {cycle_count} ({self.generation_type}) completed. ---")
            time.sleep(self.settings.delay_between_cycles)

    async def _process_project_with_retries(
        self,
        processor: ProjectProcessor,
        project_data: dict,
        project_path: Path,
        use_pose_override: bool,
        use_hands_refiner_override: bool,
        use_amateur_effect_override: bool
    ) -> bool:
        """
        Processes a single project with a retry mechanism.

        It attempts to process the project up to `max_retries` times. The run
        counters in the state manager are updated only after all retries are exhausted.
        """
        success = False
        for attempt in range(self.settings.max_retries + 1):
            if attempt > 0:
                self.logger.info(f"Retrying project {project_data['vreproID']}... (Attempt {attempt}/{self.settings.max_retries})")
                time.sleep(self.settings.retries_delay_seconds)

            self.restarter.check_and_restart(self.state_manager.get_total_runs())

            success = await processor.process(
                project_data=project_data,
                project_path=project_path,
                generation_type=self.generation_type,
                use_pose=use_pose_override,
                use_hands_refiner=use_hands_refiner_override,
                use_amateur_effect=use_amateur_effect_override,
            )

            self._increment_total_runs()

            if success:
                return True
            
            if attempt == 0:
                self.logger.info(f"No images generated for project{project_data['vreproID']}.")

        if not success:
            self.logger.error(f"Project {project_data['vreproID']} failed after {self.settings.max_retries + 1} attempts.")

        time.sleep(self.settings.delay_between_projects)

        return False

    def _get_resume_index(self, project_dirs: List[str]) -> int:
        """
        Determines the starting index for resuming a batch run.

        Reads the state to find the last processed project. If found in the
        current list of directories, its index is returned to resume from that point.

        Args:
            project_dirs (List[str]): A list of all project directory paths.

        Returns:
            The index to resume from, or 0 to start from the beginning.
        """
        state = self.state_manager.read()
        last_project = state.get(self.generation_type)

        if not last_project:
            return 0
        try:
            project_names = [Path(p).name for p in project_dirs]
            index = project_names.index(last_project)
            self.logger.debug(f"Resuming from {last_project}")
            return index
        except ValueError:
            self.logger.warning(f"Previous project '{last_project}' not found. Starting from scratch.")
            return 0

    def _update_current_project(self, project_name: str) -> None:
        """Updates the state with the currently processing project."""
        state = self.state_manager.read()
        state[self.generation_type] = project_name
        self.state_manager.write(state)
        self.logger.debug(f"State updated: {self.generation_type} = {project_name}")

    def _clear_current_project(self) -> None:
        """Clears the current project from the state after a cycle completes."""
        state = self.state_manager.read()
        if state.get(self.generation_type) is not None:
            state[self.generation_type] = None
            self.state_manager.write(state)
            self.logger.debug(f"State cleared for {self.generation_type}")

    def _increment_total_runs(self) -> None:
        """Increments the total runs counter."""
        state = self.state_manager.read()
        state["total_runs"] = state.get("total_runs", 0) + 1
        self.state_manager.write(state)

    def _record_project_result(self, success: bool) -> None:
        """Records the result of a project run."""
        state = self.state_manager.read()
        if success:
            state["successful_projects"] = state.get("successful_projects", 0) + 1
        else:
            state["failed_projects"] = state.get("failed_projects", 0) + 1
        self.state_manager.write(state)

def run_batch(
    generation_type: str,
    max_cycles: int = -1,
    donor_list: List[str] = None,
    use_pose_override: Optional[bool] = None,
    use_hands_refiner_override: Optional[bool] = None,
    use_amateur_effect_override: Optional[bool] = None,
):
    """
    Entry point to start a batch generation process.

    This function initializes and runs a `BatchOrchestrator` for the specified
    generation type and parameters. It serves as a compatible entry point
    with the previous implementation.

    Args:
        generation_type (str): The type of images to generate ('fullbody' or 'portrait').
        max_cycles (int): The maximum number of cycles to run. Defaults to -1 (infinite).
        donor_list (List[str], optional): A specific list of donor IDs to process.
        use_pose_override (Optional[bool]): Overrides the default pose setting.
        use_hands_refiner_override (Optional[bool]): Overrides the default hands refiner setting.
        use_amateur_effect_override (Optional[bool]): Overrides the default amateur effect setting.
    """
    async def main():
        orchestrator = BatchOrchestrator(
            generation_type=generation_type,
        )
        await orchestrator.run(
            max_cycles=max_cycles,
            donor_list=donor_list or [],
            use_pose_override=use_pose_override,
            use_hands_refiner_override=use_hands_refiner_override,
            use_amateur_effect_override=use_amateur_effect_override,
        )
    asyncio.run(main())