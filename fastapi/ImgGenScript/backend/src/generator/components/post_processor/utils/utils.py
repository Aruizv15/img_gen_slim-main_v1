import io
import math

from PIL import Image
from typing import Union, Tuple

def _validate_range_logic(low: float, high: float) -> Tuple[float, float]:
    """
    Validates and corrects the consistency of a (low, high) range.

    If `low` is greater than `high`, it swaps the values to ensure the
    range is always valid.

    Args:
        low (float): The lower bound of the range.
        high (float): The upper bound of the range.

    Returns:
        A tuple containing the corrected (low, high) pair.
    """
    if low > high:
        return high, low 
    else:
        return low, high
    
def _rotated_rectangle(w: float, h: float, angle: float) -> Tuple[float, float]:
    """
    Calculates the dimensions of the largest axis-aligned rectangle inside a rotated one.

    This is a helper method used to find the optimal crop dimensions after a
    rotation to avoid showing black borders. The formula is adapted from
    standard geometric solutions.

    Args:
        w (float): The width of the original rectangle.
        h (float): The height of the original rectangle.
        angle (float): The rotation angle in radians.

    Returns:
        A tuple (wr, hr) containing the width and height of the largest
        inner rectangle.
    """
    if w <= 0 or h <= 0:
        return 0, 0

    width_is_longer = w >= h
    side_long, side_short = (w, h) if width_is_longer else (h, w)

    sin_a, cos_a = abs(math.sin(angle)), abs(math.cos(angle))
    if side_short <= 2. * sin_a * cos_a * side_long or abs(sin_a - cos_a) < 1e-10:
        x = 0.5 * side_short
        wr, hr = (x / sin_a, x / cos_a) if width_is_longer else (x / cos_a, x / sin_a)
    else:
        cos_2a = cos_a * cos_a - sin_a * sin_a
        wr, hr = (w * cos_a - h * sin_a) / cos_2a, (h * cos_a - w * sin_a) / cos_2a

    return wr, hr

def _bytes_to_image(image_data: Union[bytes, Image.Image]) -> Image.Image:
    """
    Converts image data from bytes to a PIL Image object.

    If the input is already a PIL Image, it is returned directly.

    Args:
        image_data (bytes or Image.Image): The input image data.

    Returns:
        The image as a PIL.Image.Image object.

    Raises:
        TypeError: If the input data is not bytes or a PIL Image.
    """
    if isinstance(image_data, Image.Image):
        return image_data
    
    elif isinstance(image_data, bytes):
        return Image.open(io.BytesIO(image_data))
    
    else:
        raise TypeError(f"Input data must be 'bytes' or 'PIL.Image.Image', "
                        f"but received '{type(image_data)}'.")

def _image_to_bytes(image_data: Union[Image.Image, bytes], format: str = 'PNG') -> bytes:
    """
    Converts a PIL Image object back to bytes.

    If the input is already bytes, it is returned directly.

    Args:
        image_data (Image.Image or bytes): The input image object.
        format (str, optional): The image format to save as (e.g., 'PNG', 'JPEG').
            Defaults to 'PNG'.

    Returns:
        The image data as bytes.

    Raises:
        TypeError: If the input data is not a PIL Image or bytes.
    """
    if isinstance(image_data, bytes):
        return image_data
    
    elif isinstance(image_data, Image.Image):
        byte_io = io.BytesIO()
        format = format.upper()
        
        if format == 'JPEG':
            image_data.save(byte_io, format='JPEG', quality=100) 
        else:
            image_data.save(byte_io, format=format)
            
        return byte_io.getvalue()

    else:
        raise TypeError(f"Input data must be 'bytes' or 'PIL.Image.Image', "
                        f"but received '{type(image_data)}'.")