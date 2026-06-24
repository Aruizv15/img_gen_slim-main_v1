import io
import random

from PIL import Image
from typing import Union

from ..utils.utils import _validate_range_logic, _bytes_to_image

def jpeg_compression_artifacts(image: Union[Image.Image, bytes], min_quality: int = 70, max_quality: int = 90, verbose: bool = False) -> Image.Image:
    """
    Simulates JPEG compression artifacts typical of cell phone photos.

    Saves the image in JPEG with variable quality and reloads it to introduce blocking and banding.

    Args:
        image (Image.Image or bytes): The input image.
        min_quality (int, optional): Minimum compression quality. Defaults to 70.
        max_quality (int, optional): Maximum compression quality. Defaults to 90.
        verbose (bool, optional): If True, prints the applied effect details. Defaults to False.

    Returns:
        Image.Image: The image with compression artifacts.
    """
    image = _bytes_to_image(image)
    low, high = _validate_range_logic(min_quality, max_quality)
    
    quality = random.randint(low, high)
    
    if verbose:
        print(f" - Applying JPEG Compression Artifacts with quality: {quality}")
        
    byte_io = io.BytesIO()
    image.save(byte_io, format='JPEG', quality=quality)

    return Image.open(io.BytesIO(byte_io.getvalue()))