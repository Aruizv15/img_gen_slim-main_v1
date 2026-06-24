import random
import logging
import numpy as np

from pathlib import Path
from PIL import Image
from typing import Union, Optional, List, Tuple


from backend.src.config.settings import Settings, get_settings
from backend.src.utils.io import load_json_file

from .utils.utils import _bytes_to_image, _image_to_bytes
from .blocks.applicator import apply_effects_in_block
from .effects import *

settings: Settings = get_settings()

class PostProcessor:
    """
    A utility class to simulate the aesthetic of amateur smartphone photography.

    This class applies a series of optical, sensor, and compositional
    imperfections to an image to make it look less like a perfect render and
    more like a real-world photo. It supports both PIL Image objects and raw
    byte inputs/outputs for easy integration into various pipelines.
    """
    def __init__(self, seed: Optional[int] = None, logger: Optional[logging.Logger] = None) -> None:
        """
        Initializes the PostProcessor and optionally sets the random seed.

        Args:
            seed (int, optional): A seed for the random number generators to ensure
                reproducible results. Defaults to None.
            logger (logging.Logger, optional): A logger for recording process information.
        """
        if seed is not None:
            random.seed(seed)
            np.random.seed(seed)

        config_path = Path(settings.config_dir) / "post_processor"
        blocks_path = config_path / "blocks.json"
        styles_path = config_path / "styles.json"

        self.blocks = load_json_file(blocks_path)
        self.styles = load_json_file(styles_path)

        self.logger = logger

    # --- Processing Method ---

    def process(
        self, 
        image: Union[Image.Image, bytes],
        style_name: str,
        environment_type: str,
        light_temp: str,
        verbose: bool = False
    ) -> bytes:
        """
        Applies a chain of post-processing effects to an input image.

        This is the main public method of the class. It takes an image and
        contextual information, then applies a series of effects organized in
        sequential blocks (e.g., geometry, color, noise) based on a specified style.

        Args:
            image (Union[Image.Image, bytes]): The input image data.
            style_name (str): The name of the style profile to use for processing.
            environment_type (str): The environment context (e.g., 'indoor', 'outdoor').
            light_temp (str): The light temperature context ('warm', 'neutral', 'cool').
            verbose (bool, optional): If True, prints progress and details of each
                applied effect. Defaults to False.

        Returns:
            bytes: The processed image as bytes, saved in PNG format to preserve quality
            before final saving.
        """            
        if style_name not in self.styles.keys():
            raise ValueError("Invalid style name.")
        
        processed_image = _bytes_to_image(image)

        effects_config = self.styles[style_name].get("effects", {})

        # Iterate through each block of effects (e.g., geometry, color) and apply them.
        for _, block_config in self.blocks.items():
            processed_image = apply_effects_in_block(
                processed_image, block_config, effects_config, environment_type, light_temp, verbose=verbose
            )

        # Convert back to bytes for the final output.
        output_bytes = _image_to_bytes(processed_image, format='PNG') 
            
        return output_bytes
    
    def process_batch(
        self,
        images: List[Tuple[str, Union[bytes, Image.Image]]],
        style_name: str,
        environment_type: str,
        light_temp: str,
        verbose: bool = False
    ) -> List[Tuple[str, bytes]]:
        """
        Processes multiple images in a single batch operation.

        This method iterates through a list of images and applies the main
        processing logic (via `self.process`) with the specified styling
        parameters. It handles potential errors during the processing of
        individual images and reports the outcome.

        Args:
            images: A list of tuples, where each tuple contains the filename
                (str) and the image data, which can be raw bytes or a PIL
                Image object.
            style_name: The name of the style to apply (e.g., "vintage").
                The prefix "style_" will be added if missing.
            environment_type: The type of environment for processing (e.g.,
                "indoor"). The prefix "env_" will be removed if present.
            light_temp: The light temperature setting (e.g., "warm").
                The prefix "light_temp_" will be removed if present.
            verbose: If True, prints progress and error messages during
                batch processing. Defaults to False.

        Returns:
            A list of tuples, where each tuple contains the filename (str)
            and the processed image data as bytes. Images that failed
            processing are omitted from the result list.
        """
        style_key = style_name if style_name.startswith("style_") else f"style_{style_name}"
        env = environment_type.replace("env_", "") if environment_type.startswith("env_") else environment_type
        light = light_temp.replace("light_temp_", "") if light_temp.startswith("light_temp_") else light_temp

        results: List[Tuple[str, bytes]] = []
        
        if verbose:
            print(f"[POST PROCESSOR] Starting batch processing for {len(images)} image(s).")

        for i, (filename, img_data) in enumerate(images):
            if verbose:
                print(f"    [PROGRESS] Image[{i+1}/{len(images)}] Processing {filename}")

            try:
                processed = self.process(
                    img_data,
                    style_key,
                    env, light,
                    verbose=False
                )
                results.append((filename, processed))
            except Exception as e:
                print(f"    [ERROR] Failed to process {filename}: {e}")

        if verbose:
            print(f"[POST PROCESSOR] {len(results)}/{len(images)} images successfully processed.")

        return results