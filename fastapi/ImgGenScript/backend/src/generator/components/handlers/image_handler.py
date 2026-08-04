from pathlib import Path
from typing import List, Tuple, Dict, Optional

from backend.src.clients.fastapi_client import FastAPIClient
from backend.src.clients.comfyui_client import ComfyUIClient
from backend.src.utils import save_generated_images

class ImageHandler:

    def __init__(self, comfy_client: ComfyUIClient, fastapi_client: FastAPIClient):
        
        self.comfy: ComfyUIClient = comfy_client
        self.fastapi: FastAPIClient = fastapi_client

    def upload_images(
        self,
        input_dir: Optional[str] = None,
        reference_path: Optional[str] = None,
        max_dim: int = 1024,
        verbose: bool = False,
    ) -> bool:
        
        if not (input_dir or reference_path):
            return False

        if verbose:
            print(f"[UPLOAD] Input dir: {input_dir}, Ref: {reference_path}")

        success = self.fastapi.upload_images(
            input_images_directory=input_dir,
            reference_image_path=reference_path,
            max_dimension=max_dim,
        )

        if success:
            if verbose:
                print("[UPLOAD] Success")
        else:
            if verbose:
                print("[UPLOAD] Failed")
                
        return success

    def download_images(
            self,
            paths: List[Tuple[str, str, str]],
            verbose: bool = False
    ) -> List[Tuple[str, bytes]]:
        """
        Downloads generated images from the ComfyUI client based on their paths.

        This method takes a list of image file paths (as returned by the
        `generate_images` method) and fetches the image data from the ComfyUI server.

        Args:
            paths (List[Tuple[str, str, str]]): A list of tuples, where each tuple
                typically contains (filename, subfolder, type) identifying the image
                on the ComfyUI server.
            verbose (bool, optional): If True, prints status messages during the download.
                Defaults to False.

        Returns:
            List[Tuple[str, bytes]]: A list of tuples, where each tuple contains
            the filename and the raw image data in bytes. Returns an empty
            list if no images were successfully downloaded.
        """
        images = self.comfy.download_images_from_paths(paths, verbose=verbose)

        if images:
            if verbose:
                print("[DOWNLOAD] Success")
        else:
            if verbose:
                print("[DOWNLOAD] Failed")

        return images
    
    def generate_images(
        self,
        workflow: Dict,
        verbose: bool = False
    ) -> List[Tuple[str, str, str]]:
        """
        Generates images by sending a workflow to the ComfyUI client.

        This method initiates the image generation process on the ComfyUI server
        using the provided workflow configuration.

        Args:
            workflow (Dict): The ComfyUI workflow (prompt) structure defining
                the image generation task.
            verbose (bool, optional): If True, prints status messages during generation.
                Defaults to False.

        Returns:
            List[Tuple[str, str, str]]: A list of paths for the generated images,
            formatted as (filename, subfolder, type). This list is used for
            subsequent downloading. Returns an empty list on failure.
        """
        images = self.comfy.generate_images(workflow, verbose=verbose)

        if images:
            if verbose:
                print("[GENERATION] Success")
        else:
            if verbose:
                print("[GENERATION] Failed")

        return images

    def clear_all(self, verbose: bool = False) -> None:
        """
        Clears temporary input and output image directories on the backend.

        This is used for cleanup after the image generation process is complete.

        Args:
            verbose (bool, optional): If True, prints status messages during the clear operation.
                Defaults to False.
        """
        success = self.fastapi.clear_images(verbose=verbose)

        if success:
            if verbose:
                print("[CLEAR] Success")
        else:
            if verbose:
                print("[CLEAR] Failed")

    def save_images(
        self,
        output_dir: Path,
        raw_images: Optional[List[Tuple[str, bytes]]],
        processed_images: Optional[List[Tuple[str, bytes]]] = None,
        raw_suffix: str = "_raw",
        processed_suffix: str = "_amt",
        verbose: bool = False,
    ) -> None:
       
        save_generated_images(raw_images, output_dir, suffix=raw_suffix)
        if verbose:
            print(f"[SAVE] Saved {len(raw_images)} raw images to {output_dir}")
        
        if processed_images is not None:
            save_generated_images(processed_images, output_dir, suffix=processed_suffix)
            if verbose:
                print(f"[SAVE] Saved {len(processed_images)} processed images to {output_dir}")
