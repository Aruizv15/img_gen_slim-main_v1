import os
import io
import logging
from typing import Optional

from .base_client import BaseAPIClient
from backend.src.utils.image import resize_image_if_needed

class FastAPIClient(BaseAPIClient):
    """
    A client for interacting with the FastAPI backend service.

    This class provides a consistent interface similar to ComfyUIClient,
    with unified HTTP handling, error management, and response parsing.
    It communicates with the FastAPI server via HTTP POST/GET.
    """
    def __init__(
        self,
        server_address: str = "127.0.0.1:8000",
        timeout: int = 15,
        client_id: Optional[str] = None,
        logger: Optional[logging.Logger] = None
    ):
        """
        Initializes the FastAPIClient with server connection.

        Args:
            server_address (str, optional): FastAPI server address (host:port).
            timeout (int, optional): HTTP request timeout in seconds.
            client_id (str, optional): Optional custom client ID. Auto-generated if None.
            logger (str, optional): Optional custom logger.
        """
        super().__init__(server_address, timeout, client_id, logger)

    def health_check(self, verbose: bool = False) -> bool:
        """
        Performs a health check on the FastAPI server.

        Args:
            verbose (bool, optional): If True, prints status.

        Returns:
            True if server is healthy.
        """
        result = self.http.get("/health")
        if result["status"] == "success":
            if verbose: print("[HEALTH] Server is healthy.")
            return True
        if verbose: print(f"[HEALTH] Unhealthy: {result.get('message')}")
        return False

    def upload_images(
        self,
        input_images_directory: Optional[str] = None,
        reference_image_path: Optional[str] = None,
        max_dimension: int = 1024,
    ) -> bool:
        """
        Uploads images to the FastAPI server's /upload_images endpoint.

        This method prepares and sends images from a local directory and/or a single
        reference image. Images are resized if they exceed `max_dimension`.

        Args:
            input_images_directory (str, optional): Path to a directory containing input images.
            reference_image_path (str, optional): Path to a single reference image.
            max_dimension (int, optional): The maximum dimension for image resizing.

        Returns:
            True if the upload was successful, False otherwise.
        """
        files = {}
        file_list = []  

        # --- Folder Images ---
        if input_images_directory:
            if not os.path.isdir(input_images_directory):
                return False

            for filename in os.listdir(input_images_directory):
                file_path = os.path.join(input_images_directory, filename)

                if os.path.isfile(file_path):
                    try:
                        img_bytes = resize_image_if_needed(file_path, max_dimension)
                        buf = io.BytesIO(img_bytes)
                        file_list.append(("images", (filename, buf, "image/png")))
                    except Exception as e:
                        pass

        # --- Pose Reference ---
        if reference_image_path:
            if not os.path.isfile(reference_image_path):
                return False

            try:
                img_bytes = resize_image_if_needed(reference_image_path, max_dimension)
                buf = io.BytesIO(img_bytes)
                file_list.append(("reference", (os.path.basename(reference_image_path), buf, "image/png")))
            except Exception as e:
                return False

        if not file_list:
            return False

        files = file_list

        result = self.http.post("/upload_images", files=files)

        # Close file buffers
        for _, (_, buf, _) in file_list:
            try:
                buf.close()
            except:
                pass

        if result["status"] == "success":
            return True
        else:
            return False
    
    def clear_images(self, verbose: bool = False) -> bool:
        """
        Clears all images from shared directories via /clear_images endpoint.

        Args:
            verbose (bool, optional): If True, prints the server response message.

        Returns:
            True if successful, False otherwise.
        """
        result = self.http.post("/clear_images")
        if result["status"] == "success":
            if verbose: print(f"[CLEAR] {result['data'].get('message', 'Images cleared')}")
            return True
        if verbose: print(f"[CLEAR] Failed: {result.get('message')}")
        return False
    
    def free_vram(self, verbose: bool = False) -> bool:
        """
        Requests FastAPI to free VRAM in ComfyUI via the /free_vram endpoint.

        Args:
            verbose (bool, optional): If True, prints success/error messages with VRAM details.

        Returns:
            True if successful, False otherwise.
        """
        result = self.http.post("/free_vram")
        if result["status"] == "success":
            if verbose:
                details = result["data"].get("details", {})
                freed = details.get("vram_freed_gb", 0)
                current = details.get("vram_current_gb", 0)
                print(f"[VRAM] Freed {freed:.2f} GB -> {current:.2f} GB left")
            return True
        if verbose:
            print(f"[VRAM] Error: {result.get('message')}")
        return False

    def restart_comfyui(self, token: str, verbose: bool = False, timeout: Optional[int] = None) -> bool:
        """
        Restarts the ComfyUI container via FastAPI's /restart_comfyui endpoint.

        This requires a valid Bearer token configured in the FastAPI server.

        Args:
            token (str): The Bearer token for authorization.
            verbose (bool, optional): If True, prints success/error messages.
            timeout (int, optional): Custom timeout in seconds. Uses default if None.

        Returns:
            True if restart was successful, False otherwise.
        """
        headers = {"Authorization": f"Bearer {token}"}
        result = self.http.post("/restart_comfyui", headers=headers, timeout=timeout or self.timeout)
        if result["status"] == "success":
            if verbose: print("[RESTART] ComfyUI restarted.")
            return True
        if verbose:
            msg = result.get("message", "Restart failed")
            detail = result.get("detail", "")
            print(f"[RESTART] Error: {msg}" + (f" - {detail}" if detail else ""))
        return False