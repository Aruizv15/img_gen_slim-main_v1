import os
import sys
import asyncio
import logging

from io import StringIO
from textual.app import App, ComposeResult
from pathlib import Path
from textual.widgets import Header, Footer, Static, Button, Checkbox, Input, Label, RichLog
from textual.containers import Container, VerticalScroll, Horizontal
from textual.validation import Validator, Integer

from backend.src.config.settings import Settings, get_settings

SETTINGS: Settings = get_settings()

if SETTINGS.backend_root not in sys.path:
    sys.path.insert(0, SETTINGS.backend_root)

try:
    from backend.src.batch.orchestrator import run_batch
    from backend.src.clients.comfyui_client import ComfyUIClient
    from backend.src.utils import organize_approved_images, load_json_file, save_json_file
except ImportError as e:
    logging.error(f"Error importing functions: {e}")
    sys.exit(1)

class OutputRedirector(StringIO):
    def __init__(self, log_widget: RichLog):
        super().__init__()
        self.log_widget = log_widget
        self.buffer = []

    def write(self, s: str):
        if '\n' in s:
            parts = s.split('\n')
            self.buffer.append(parts[0])
            self.log_widget.write("".join(self.buffer) + "\n")
            self.buffer = [parts[1]] if len(parts) > 1 and parts[1].strip() else []
        else:
            self.buffer.append(s)

    def flush(self):
        if self.buffer:
            self.log_widget.write("".join(self.buffer))
            self.buffer = []

class DonorListValidator(Validator):
    """
    Validates a string to ensure it contains only integers separated by commas.
    An empty string is considered valid.
    """
    def validate(self, value: str) -> None:
        if not value.strip():
            return self.success()

        parts = value.split(',')
        for part in parts:
            try:
                int(part.strip())
            except ValueError:
                self.failure(f"'{part.strip()}' is not a valid number.")
        return self.success()

class BatchApp(App):
    """A Textual application to run batch jobs for image generation."""

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("d", "toggle_dark", "Toggle dark mode"),
        ("a", "approved", "Export Approved"),
    ]

    CSS_PATH = "app.css"

    async def _run_fullbody_batch_async(self, max_cycles: int, donor_list: list[str], use_pose: bool, use_hands_refiner: bool, use_amateur_effect: bool) -> None:
        """ Async wrapper for fullbody_batch"""
        try:
            self.log("Starting Fullbody batch...")
            await asyncio.to_thread(run_batch, generation_type='fullbody', max_cycles=max_cycles, donor_list=donor_list, use_pose_override=use_pose, use_hands_refiner_override=use_hands_refiner, use_amateur_effect_override=use_amateur_effect)
            self.log("Fullbody batch completed.")
            self.notify("Fullbody batch completed.", timeout=3)
        except asyncio.CancelledError:
            self.log("Fullbody batch was cancelled.")
            self.notify("Fullbody batch cancelled.", timeout=3)

        self._set_run_button_enabled(True)

    async def _run_portrait_batch_async(self, max_cycles: int, donor_list: list[str]) -> None:
        """ Async wrapper for portrait_batch"""
        try:
            self.log(f"Starting Portrait batch")
            await asyncio.to_thread(run_batch, generation_type='portrait', max_cycles=max_cycles, donor_list=donor_list)
            self.log("Portrait batch completed.")
            self.notify("Portrait batch completed.", timeout=3)
        except asyncio.CancelledError:
            self.log("Portrait batch was cancelled.")
            self.notify("Portrait batch cancelled.", timeout=3)

        self._set_run_button_enabled(True)

    async def _run_both_async(self, max_cycles_fb: int, max_cycles_pt: int, donor_list: list[str], use_pose: bool, use_hands_refiner: bool, use_amateur_effect: bool) -> None:
        """
        Asynchronous wrapper to run fullbody_batch and portrait_batch
        in alternating cycles until both reach their maximum.
        """
        fullbody_cycles_done = 0
        portrait_cycles_done = 0

        self.log(f"Starting combined batch with Fullbody: {max_cycles_fb} cycles, Portrait: {max_cycles_pt} cycles.")
        self.notify("Starting combined batches...", timeout=3)

        while fullbody_cycles_done < max_cycles_fb or portrait_cycles_done < max_cycles_pt or max_cycles_fb == -1 or max_cycles_pt == -1:
            if fullbody_cycles_done < max_cycles_fb or max_cycles_fb == -1 :
                self.log(f"Starting Fullbody batch cycle {fullbody_cycles_done + 1}/{max_cycles_fb}")
                try:
                    await asyncio.to_thread(run_batch, generation_type='fullbody', max_cycles=1, donor_list=donor_list, use_pose_override=use_pose, use_hands_refiner_override=use_hands_refiner, use_amateur_effect_override=use_amateur_effect)
                    fullbody_cycles_done += 1
                    self.log(f"Fullbody batch cycle {fullbody_cycles_done} completed.")
                    self.notify(f"Fullbody cycle {fullbody_cycles_done}/{max_cycles_fb} completed.", timeout=1)
                except asyncio.CancelledError:
                    self.log("Fullbody batch was cancelled.")
                    self.notify("Fullbody batch cancelled.", timeout=3)
                    break
                except Exception as e:
                    self.log(f"Error in Fullbody batch cycle {fullbody_cycles_done + 1}: {e}", severity="error")
                    self.notify(f"Fullbody cycle error: {e}", severity="error", timeout=5)
                    break

            if portrait_cycles_done < max_cycles_pt or max_cycles_pt == -1:
                self.log(f"Starting Portrait batch cycle {portrait_cycles_done + 1}/{max_cycles_pt}")
                try:
                    await asyncio.to_thread(run_batch, generation_type='portrait', max_cycles=1, donor_list=donor_list)
                    portrait_cycles_done += 1
                    self.log(f"Portrait batch cycle {portrait_cycles_done} completed.")
                    self.notify(f"Portrait cycle {portrait_cycles_done}/{max_cycles_pt} completed.", timeout=1)
                except asyncio.CancelledError:
                    self.log("Portrait batch was cancelled.")
                    self.notify("Portrait batch cancelled.", timeout=3)
                    break
                except Exception as e:
                    self.log(f"Error in Portrait batch cycle {portrait_cycles_done + 1}: {e}", severity="error")
                    self.notify(f"Portrait cycle error: {e}", severity="error", timeout=5)
                    break

            await asyncio.sleep(0.01)

        self._set_run_button_enabled(True)

        if fullbody_cycles_done == max_cycles_fb and portrait_cycles_done == max_cycles_pt:
            self.log("Both batches completed all cycles.")
            self.notify("All batches completed.", timeout=3, severity="information")
        else:
            self.log("Batch processing stopped before completion (possibly cancelled or error).")
            self.notify("Batch processing stopped.", timeout=3, severity="warning")

    def compose(self) -> ComposeResult:
        yield Header()
        yield Footer()
        with Horizontal(id="main-horizontal-container"):
            with VerticalScroll(id="left-panel"):
                yield Static("Welcome to the Model Image Generator!", classes="title")
                yield Static("Select options to run your functions.", classes="description")

                with Horizontal(id="checkbox-options"):
                    yield Checkbox("[b]Fullbody[/b]", id="checkbox-fullbody", value=False)
                    yield Checkbox("[b]Portrait[/b]", id="checkbox-portrait", value=False)

                with Container(id="fullbody-controls"):
                    yield Label("Fullbody Options:")
                    yield Input(
                        placeholder="Cycles (-1 for infinite)",
                        value="1",
                        id="input-fullbody-cycles",
                        validators=[Integer(minimum=-1)]
                    )
                    with Horizontal(id="fullbody-checkboxes"):
                        yield Checkbox("Use Pose", id="checkbox-fullbody-use-pose", value=False)
                        yield Checkbox("Hands Refiner", id="checkbox-fullbody-hands-refiner", value=False)
                        yield Checkbox("Amateur Effect", id="checkbox-amateur-effect", value=False)

                with Container(id="portrait-controls"):
                    yield Label("Portrait Options:")
                    yield Input(
                        placeholder="Cycles (-1 for infinite)",
                        value="1",
                        id="input-portrait-cycles",
                        validators=[Integer(minimum=-1)]
                    )

                with Container(id="donor-list-controls"):
                    yield Label("Model List (comma-separated numbers, e.g., 1,2,3):")
                    yield Input(
                        placeholder="E.g.: 609, 1673, 100",
                        id="input-donor-list",
                        validators=[DonorListValidator()]
                    )

                with Horizontal(id="action-buttons"):
                    yield Button("Start Execution", variant="primary", id="run-button")
                    yield Button("Stop Execution", variant="error", id="stop-button")

            with VerticalScroll(id="right-panel"):
                yield RichLog(id="terminal-output", classes="terminal-output-style")

    def on_mount(self) -> None:
        """Called once the app is mounted."""
        try:
            state_file_path = Path(SETTINGS.log_dir) / "batch_state.json"
            initial_state = {
                "fullbody": None,
                "portrait": None,
                "total_runs": 0,
                "successful_projects": 0,
                "failed_projects": 0
            }
            save_json_file(str(state_file_path), initial_state)
            self.log("Batch state has been reset (runs counters set to 0).")
        except Exception as e:
            self.log(f"Could not reset batch state file: {e}", severity="error")

        terminal_output_log = self.query_one("#terminal-output", RichLog)

        self._original_stdout = sys.stdout
        self._original_stderr = sys.stderr

        sys.stdout = OutputRedirector(terminal_output_log)
        sys.stderr = OutputRedirector(terminal_output_log)

        self.log("Textual app started. Output will appear here.")

        root_logger = logging.getLogger()

        for handler in root_logger.handlers[:]:
            if isinstance(handler, logging.StreamHandler):
                root_logger.removeHandler(handler)

        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        root_logger.addHandler(handler)

        root_logger.setLevel(logging.INFO)

    def _set_run_button_enabled(self, enabled: bool) -> None:
        """Enables or disables the 'Run Batches' button."""
        run_button = self.query_one("#run-button", Button)
        run_button.disabled = not enabled

    def action_quit(self) -> None:
        """Quits the application."""
        sys.stdout = self._original_stdout
        sys.stderr = self._original_stderr
        self.stop_generation()
        self.exit()

    def action_approved(self) -> None:
        """
        Action method called when the 'a' key is pressed.
        This will execute the export_approved function in a worker thread.
        """
        self.notify("Executing export_approved...", timeout=3)
        self.log("Action 'approved' triggered. Calling organize_approved_images.")
        self.run_worker(self.export_approved()) # Ejecuta export_approved en un hilo separado

    async def export_approved(self) -> None:
        """
        Placeholder function for exporting approved items.
        Replace this with your actual logic. This function will be run in a worker thread.
        """
        self.log("Starting export_approved process...")
        organize_approved_images(SETTINGS.images_dir, SETTINGS.approved_dir)
        self.log("Organize approved images process completed.")
        self.notify("Organize approved images completed successfully!", severity="information", timeout=3)


    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Called when a button is pressed."""
        if event.button.id == "run-button":
            self.run_selected_batches()
        elif event.button.id == "stop-button":
            self.action_quit()

    def parse_donor_list(self, raw_input: str) -> list[str]:
        """
        Converts a string of int into a list of formatted OVOD00000 IDs 
        """
        if not raw_input.strip():
            return []

        parts = [part.strip() for part in raw_input.split(',')]

        donor_ids = []
        for part in parts:
            try:
                num = int(part)
                donor_ids.append(f"OVOD{num:05d}")
            except ValueError:
                self.log(f"Warning: '{part}' is not a valid number for the donor list. It will be skipped.")
        return donor_ids

    def run_selected_batches(self) -> None:
        """Collects parameters and runs the selected batch functions."""
        fullbody_checkbox = self.query_one("#checkbox-fullbody", Checkbox)
        portrait_checkbox = self.query_one("#checkbox-portrait", Checkbox)

        fullbody_cycles_input = self.query_one("#input-fullbody-cycles", Input)
        portrait_cycles_input = self.query_one("#input-portrait-cycles", Input)
        fullbody_use_pose_checkbox = self.query_one("#checkbox-fullbody-use-pose", Checkbox)
        fullbody_hands_refiner_checkbox = self.query_one("#checkbox-fullbody-hands-refiner", Checkbox)
        amateur_effect_checkbox = self.query_one("#checkbox-amateur-effect", Checkbox)
        donor_list_input = self.query_one("#input-donor-list", Input)

        should_run_fullbody = fullbody_checkbox.value
        should_run_portrait = portrait_checkbox.value

        for input_widget in [fullbody_cycles_input, portrait_cycles_input, donor_list_input]:
            if input_widget.validators:
                validation_result = input_widget.validators[0].validate(input_widget.value)
                if not validation_result.is_valid:
                    self.notify(f"Validation Error: {validation_result.failure_description}", severity="error")
                    return

        fullbody_cycles = int(fullbody_cycles_input.value) if fullbody_cycles_input.value else -1
        portrait_cycles = int(portrait_cycles_input.value) if fullbody_cycles_input.value.strip() != '' else -1
        fullbody_use_pose = fullbody_use_pose_checkbox.value
        fullbody_use_hands_refiner = fullbody_hands_refiner_checkbox.value
        use_amateur_effect = amateur_effect_checkbox.value

        donor_list_processed = self.parse_donor_list(donor_list_input.value)
        donor_list_for_display = ", ".join(donor_list_processed)

        if not should_run_fullbody and not should_run_portrait:
            self.notify("No function selected. Please choose at least one.", severity="warning", timeout=3)
            return

        self._set_run_button_enabled(False)

        self.notify("Starting selected tasks...", timeout=3)
        self.log("Starting selected tasks...")

        def on_batch_complete(worker_result):
            self._set_run_button_enabled(True)
            self.log(f"Batch worker finished with state: {worker_result.state}")

        if should_run_fullbody and should_run_portrait:
            self.log(f"Initiated Fullbody and Portrait batch for {fullbody_cycles} cycles and {portrait_cycles} cycles with use_pose={fullbody_use_pose}, hands_refiner={fullbody_use_hands_refiner}, post_processing={use_amateur_effect} and donors: {donor_list_for_display} via async wrapper.")
            worker = self.run_worker(
                self._run_both_async(
                max_cycles_fb=fullbody_cycles,
                max_cycles_pt=portrait_cycles,
                donor_list=donor_list_processed,
                use_pose=fullbody_use_pose,
                use_hands_refiner=fullbody_use_hands_refiner,
                use_amateur_effect=use_amateur_effect)
            )

        elif should_run_fullbody:
            self.log(f"Initiated Fullbody batch for {fullbody_cycles} cycles with use_pose={fullbody_use_pose}, hands_refiner={fullbody_use_hands_refiner}, post_processing={use_amateur_effect} and donors: {donor_list_for_display} via async wrapper.")
            worker = self.run_worker(
                self._run_fullbody_batch_async(
                max_cycles=fullbody_cycles,
                donor_list=donor_list_processed,
                use_pose=fullbody_use_pose,
                use_hands_refiner=fullbody_use_hands_refiner,
                use_amateur_effect=use_amateur_effect)
            )
            
        elif should_run_portrait:
            self.log(f"Initiated Portrait batch for {portrait_cycles} cycles with donors: {donor_list_for_display} via async wrapper.")
            worker = self.run_worker(
                self._run_portrait_batch_async( 
                    max_cycles=portrait_cycles,
                    donor_list=donor_list_processed)
            )
        
        else: 
            self.notify("No valid batch configuration to start.", severity="warning", timeout=3)
            return

        #worker.on_complete(on_batch_complete)
            
    def stop_generation(self):
        self.notify("Stop Generation", timeout=3)
        comfyui_client = ComfyUIClient(SETTINGS.comfyui_server_address)
        success = comfyui_client.interrupt_generation()
        self.log(f"Interrupted ComfyUI: {success}")

if __name__ == "__main__":
    app = BatchApp()
    app.run()