from pathlib import Path
from typing import List, Tuple, Dict, Optional

from backend.src.clients.fastapi_client import FastAPIClient
from backend.src.clients.comfyui_client import ComfyUIClient
from backend.src.utils import save_generated_images

class ImageHandler:
    """
    Coordinates image-related operations across different clients.

    This class centralizes the logic for handling the image lifecycle within the
    generation process. It acts as a facade, using the `FastAPIClient` to manage
    uploads and cleanup of temporary images, and the `ComfyUIClient` to handle
    the download of final, generated images.

    Key responsibilities:
    - Uploading input and reference images to the backend via the FastAPI client.
    - Downloading generated output images from ComfyUI.
    - Clearing temporary image directories on the backend.
    """
    def __init__(self, comfy_client: ComfyUIClient, fastapi_client: FastAPIClient):
        """
        Initializes the ImageHandler with required client instances.

        Args:
            comfy_client: The client used for interacting with the ComfyUI server
                (e.g., generating and downloading images).
            fastapi_client: The client used for interacting with the FastAPI backend
                (e.g., uploading input images and clearing temporary directories).
        """
        self.comfy: ComfyUIClient = comfy_client
        self.fastapi: FastAPIClient = fastapi_client

    def upload_images(
        self,
        input_dir: Optional[str] = None,
        reference_path: Optional[str] = None,
        max_dim: int = 1024,
        verbose: bool = False,
    ) -> bool:
        """
        Upload input and/or reference images to the FastAPI backend.

        This method prepares the images for generation by uploading them to the
        backend's temporary storage, optionally resizing them if they exceed
        the specified maximum dimension.

        Args:
            input_dir (str, optional): The directory containing input images to be uploaded.
                Defaults to None.
            reference_path (str, optional): The file path of a single reference image
                (e.g., for pose or style) to be uploaded. Defaults to None.
            max_dim (int, optional): The maximum dimension (width or height) for
                resizing images before upload. Images larger than this will be resized.
                Defaults to 1024.
            verbose (bool, optional): If True, prints status messages during the upload.
                Defaults to False.

        Returns:
            bool: True if at least one image was specified and the upload
            succeeded via the FastAPI client, False otherwise.
        """
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
        """
        Saves generated image data (raw and/or processed) to the local filesystem.

        This method uses a utility function to write the image data (bytes)
        to the specified output directory, applying an optional suffix to the filenames.

        Args:
            output_dir (Path): The local directory path where the images will be saved.
            raw_images (Optional[List[Tuple[str, bytes]]]): A list of tuples containing
                the filename and image data (bytes) for the raw generated images.
                Can be None if only processed images exist.
            processed_images (Optional[List[Tuple[str, bytes]]]): A list of tuples
                containing the filename and image data (bytes) for the processed images.
                Defaults to None.
            raw_suffix (str, optional): The suffix to append to the filenames of
                the raw images before the file extension. Defaults to "_raw".
            processed_suffix (str, optional): The suffix to append to the filenames
                of the processed images before the file extension. Defaults to "_amt".
            verbose (bool, optional): If True, prints status messages regarding the
                number of files saved and the output directory. Defaults to False.
        """
        save_generated_images(raw_images, output_dir, suffix=raw_suffix)
        if verbose:
            print(f"[SAVE] Saved {len(raw_images)} raw images to {output_dir}")
        
        if processed_images is not None:
            save_generated_images(processed_images, output_dir, suffix=processed_suffix)
            if verbose:
                print(f"[SAVE] Saved {len(processed_images)} processed images to {output_dir}")