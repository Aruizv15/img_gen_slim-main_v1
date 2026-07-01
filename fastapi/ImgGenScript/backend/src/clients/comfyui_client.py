import sys
import logging
from typing import List, Dict, Any, Optional, Tuple

from .base_client import BaseAPIClient
from ..generator.components.workflow.comfyui_workflow import ComfyUIWorkflow
from .utils.comfyui_web_socket import ComfyUIWebSocket
from backend.src.config.settings import Settings, get_settings

SETTINGS: Settings = get_settings()

class ComfyUIClient(BaseAPIClient):
    """
    A client for interacting with a ComfyUI server.

    This class encapsulates the logic for loading a ComfyUI workflow,
    modifying it with dynamic arguments, queuing it for generation, and
    retrieving the resulting images. It communicates with the ComfyUI
    server via HTTP and WebSockets.
    """

    def __init__(
        self,
        server_address: str = "127.0.0.1:8188",
        timeout: int = 15,
        client_id: Optional[str] = None,
        logger: Optional[logging.Logger] = None
    ):
        """
        Initialize the ComfyUI client.

        Args:
            server_address (str, optional): ComfyUI server address in the form ``host:port``.
                                           Defaults to "127.0.0.1:8188".
            timeout (int, optional): HTTP request timeout in seconds. Defaults to 15.
            client_id (str, optional): Custom client ID for WebSocket tracking.
                                       If None, a random UUID will be generated.
            logger (logging.Logger, optional): Custom logger instance. If None, uses the default logger.
        """
        super().__init__(server_address, timeout, client_id, logger)
    
    # --- API Endpoints (HTTP) ---

    def health_check(self, verbose: bool = False) -> bool:
        """
        Performs a health check on the ComfyUI server.

        Uses the /object_info endpoint to verify server availability.
        This endpoint is lightweight and always available.

        Args:
            verbose (bool, optional): If True, prints status.

        Returns:
            True if server is healthy.
        """
        result = self.http.get("/object_info")
        if result["status"] == "success":
            if verbose: print("[HEALTH] ComfyUI server is healthy.")
            return True
        if verbose: print(f"[HEALTH] Unhealthy: {result.get('message')}")
        return False

    def queue_prompt(self, prompt: Dict) -> Dict:
        """
        Sends the current workflow to the ComfyUI server to be queued.

        Args:
            prompt (Dict): The ComfyUI workflow to queue.

        Returns:
            A dictionary containing the server's response, including the 'prompt_id'.
        """
        payload = {"prompt": prompt, "client_id": self.client_id}
        return self.http.post("/prompt", data=payload)
    
    def get_history(self, prompt_id: str) -> Dict:
        """
        Retrieves the execution history for a specific prompt ID.

        Args:
            prompt_id (str): The ID of the prompt to get the history for.

        Returns:
            A dictionary containing the execution history data.
        """
        return self.http.get(f"/history/{prompt_id}")
    
    def get_image(self, filename: str, subfolder: str, folder_type: str) -> bytes:
        """
        Fetches a generated image from the ComfyUI server.

        Args:
            filename (str): The name of the image file.
            subfolder (str): The subfolder where the image is located.
            folder_type (str): The type of folder (e.g., 'output', 'input').

        Returns:
            The image data in bytes.
        """
        params = {"filename": filename, "subfolder": subfolder, "type": folder_type}
        response = self.http.session.get(
            f"http://{self.server_address}/view",
            params=params,
            timeout=self.timeout
        )
        response.raise_for_status()
        return response.content
    
    def interrupt_generation(self, verbose: bool = False) -> bool:
        """
        Sends an interrupt request to the ComfyUI server.

        Args:
            verbose (bool, optional): If True, prints confirmation or error messages.

        Returns:
            True if the request was sent successfully, False otherwise.
        """
        result = self.http.post("/interrupt", data={})
        if result["status"] == "success":
            if verbose: print("Interrupt sent.")
            return True
        if verbose: print(f"Interrupt failed: {result.get('message')}")
        return False

    def free_comfyui_memory(self, unload_models: bool = True, free_memory: bool = True, verbose: bool = False) -> bool:
        """
        Sends a request to ComfyUI to free up GPU memory.

        Args:
            unload_models (bool, optional): If True, instructs the server to unload models from VRAM.
            free_memory (bool, optional): If True, instructs the server to release cached memory.
            verbose (bool, optional): If True, prints confirmation or error messages.

        Returns:
            True if the request was sent successfully, False otherwise.
        """
        result = self.http.post("/free", json={"unload_models": unload_models, "free_memory": free_memory})
        if result["status"] == "success":
            if verbose: print("[FREE MEM] Memory freed.")
            return True
        if verbose: print(f"[FREE MEM] Failed: {result.get('message')}")
        return False

    # --- Execution Flow ---

    def run_workflow(self, workflow: Dict, verbose: bool = False) -> str:
        """
        Executes the workflow and waits for completion.

        This method queues the prompt and listens to WebSocket messages from the
        server to track the execution progress until it is complete.

        Args:
            workflow (Dict): The ComfyUI workflow to execute.
            verbose (bool, optional): If True, prints the current processing node.

        Returns:
            The `prompt_id` of the executed workflow.
        """
        result = self.queue_prompt(workflow)
        if result["status"] == "error":
            raise RuntimeError(f"Queue failed: {result['message']} | Detail: {result.get('detail', 'No detail')}")

        prompt_id = result["data"]["prompt_id"]

        def print_node(prompt_id: str, node_id: str):
            if verbose:
                title = workflow.get(node_id, {}).get("_meta", {}).get("title", "Unknown")
                sys.stdout.write(f"\r[NODE]: {title}... ")
                sys.stdout.flush()

        def on_complete():
            if verbose: print("[GENERATION END].")

        with ComfyUIWebSocket(
            server_address=self.server_address,
            client_id=self.client_id,
            prompt_id=prompt_id,
            on_node_change=print_node if verbose else None,
            on_complete=on_complete if verbose else None,
            timeout=SETTINGS.interrupt_after_seconds + 60
        ) as ws:
            if not ws.wait_for_completion():
                raise RuntimeError("Run failed")

        return prompt_id

    def get_generated_image_paths(self, prompt_id: str) -> List[Tuple[str, str, str]]:
        """
        Extract logical paths of images generated by a completed prompt.

        Args:
            prompt_id (str): The prompt ID returned by ``run_workflow``.

        Returns:
            List[Tuple[str, str, str]]: List of tuples containing
                ``(filename, subfolder, folder_type)`` for each generated image.
                Returns an empty list if no history or no images are found.
        """
        history = self.get_history(prompt_id)
        if not history or prompt_id not in history.get("data", {}):
            return []

        images = []

        for output in history.get("data", {}).get(prompt_id, {}).get("outputs", {}).values():
            for img in output.get("images", []):
                if img.get("filename"):
                    images.append((img["filename"], img.get("subfolder", ""), img.get("type", "")))
        return images
    
    def generate_images(
        self,
        workflow: Dict,
        verbose: bool = False
    ) -> List[Tuple[str, str, str]]:
        """
        Run a workflow and return the logical paths of all generated images.

        Convenience wrapper that combines ``run_workflow`` + ``get_generated_image_paths``.

        Args:
            workflow (Dict): The ComfyUI workflow to execute.
            verbose (bool, optional): If True, prints progress information. Defaults to False.

        Returns:
            List[Tuple[str, str, str]]: List of ``(filename, subfolder, type)`` tuples
                                        for the generated output images.
        """
        prompt_id = self.run_workflow(workflow, verbose=verbose)
        return self.get_generated_image_paths(prompt_id)
    
    def download_images_from_paths(
        self,
        paths: List[Tuple[str, str, str]],
        verbose: bool = False
    ) -> List[Tuple[str, bytes]]:
        """
        Download image bytes from a list of logical paths.

        Only images with ``folder_type == "output"`` are downloaded.

        Args:
            paths (List[Tuple[str, str, str]]): List of ``(filename, subfolder, type)`` tuples.
            verbose (bool, optional): If True, prints download status per file. Defaults to False.

        Returns:
            List[Tuple[str, bytes]]: List of tuples containing the filename and its raw image data.
        """
        images = []
        for filename, subfolder, folder_type in paths:
            if folder_type != "output":
                continue
            try:
                data = self.get_image(filename, subfolder, folder_type)
                images.append((filename, data))
                if verbose:
                    print(f"[IMG] Downloaded: {filename}")
            except Exception as e:
                if verbose:
                    print(f"[IMG] Failed {filename}: {e}")
        return images

    # --- Helper Methods ---

    @staticmethod
    def load_prompt_template(prompt_path: str) -> str:
        """
        Loads a prompt template from a text file.

        Args:
            prompt_path (str): The file path to the prompt template.

        Returns:
            The content of the file as a string.
        """
        with open(prompt_path, "r", encoding="utf-8") as f:
            return f.read().strip()

    @staticmethod
    def format_str_with_dict(dictionary: Dict, text_string: str) -> str:
        """
        Formats a string using placeholders from a dictionary.

        Args:
            dictionary (Dict): A dictionary containing key-value pairs for formatting.
            text_string (str): The string to format, containing placeholders like {key}.

        Returns:
            The formatted string, or an error message if formatting fails.
        """
        try:
            return text_string.format(**dictionary)
        except KeyError as e:
            return f"Error: The key '{e}' was not found in the dictionary to format the string."
        except Exception as e:
            return f"An error occurred during formatting: {e}"
