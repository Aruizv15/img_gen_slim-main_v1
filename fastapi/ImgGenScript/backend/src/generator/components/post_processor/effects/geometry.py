import math
import random

from PIL import Image
from typing import Union

from ..utils.utils import _validate_range_logic, _rotated_rectangle, _bytes_to_image

def random_rotation(image: Union[Image.Image, bytes], max_angle: float = 3, verbose: bool = False) -> Image.Image:
    """
    Applies a small random rotation to simulate a tilted horizon.
    Now with zoom and crop to avoid black borders.

    Args:
        image (Image.Image): The input image.
        max_angle (float, optional): The maximum rotation angle in degrees.
            Defaults to 3.
        verbose (bool, optional): If True, prints the applied effect details. Defaults to False.

    Returns:
        The rotated, zoomed, and cropped image (same size as input).
    """
    image = _bytes_to_image(image)

    original_w, original_h = image.size
    angle = random.uniform(-max_angle, max_angle)

    if verbose:
        print(f" - Applying Rotation: {angle:.2f} degrees")

    rotated_img = image.rotate(angle, resample=Image.BICUBIC, expand=True)

    # Calculate the largest possible crop area that avoids the black corners.
    wr, hr = _rotated_rectangle(original_w, original_h, math.radians(angle))

    # Crop the rotated image around its center to the calculated safe dimensions.
    rotated_w, rotated_h = rotated_img.size

    left = (rotated_w - wr) / 2
    top = (rotated_h - hr) / 2
    right = left + wr
    bottom = top + hr
    cropped_img = rotated_img.crop((left, top, right, bottom))

    # Resize the cropped image back to the original dimensions.
    final_img = cropped_img.resize((original_w, original_h), resample=Image.BICUBIC)

    return final_img

def random_crop(image: Union[Image.Image, bytes], min_crop: float = 0.95, max_crop: float = 1.0, verbose: bool = False) -> Image.Image:
    """
    Applies a random off-center crop to simulate casual framing.

    The image is cropped and then resized back to its original dimensions.

    Args:
        image (Image.Image): The input image.
        min_crop (float, optional): The minimun crop scale factor. Defaults to 0.95.
        max_crop (float, optional): The maximun crop scale factor. Defaults to 1.0.
        verbose (bool, optional): If True, prints the applied effect details. Defaults to False.

    Returns:
        The cropped and resized image.
    """
    image = _bytes_to_image(image)
    low, high = _validate_range_logic(min_crop, max_crop)

    original_w, original_h = image.size
    scale = random.uniform(low, high)
    
    if verbose:
        print(f" - Applying Random Crop with scale: {scale:.2f}")

    new_w, new_h = int(original_w * scale), int(original_h * scale)
    
    left = random.randint(0, original_w - new_w)
    top = random.randint(0, original_h - new_h)

    cropped_image = image.crop((left, top, left + new_w, top + new_h))
    return cropped_image.resize((original_w, original_h), Image.Resampling.LANCZOS)
