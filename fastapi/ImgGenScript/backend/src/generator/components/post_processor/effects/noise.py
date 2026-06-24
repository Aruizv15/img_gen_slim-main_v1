import cv2
import random
import numpy as np

from PIL import Image, ImageFilter
from typing import Union

from ..utils.utils import _validate_range_logic, _bytes_to_image

def blur(image: Union[Image.Image, bytes], min_kernel_size: int = 3, max_kernel_size: int = 5, verbose: bool = False) -> Image.Image:
    """
    Applies a slight Gaussian blur to the image.

    Args:
        image (Image.Image): The input image.
        min_kernel_size (int, optional): Minimum kernel size (blur intensity).
            Defaults to 3.
        max_kernel_size (int, optional): Maximum kernel size (blur intensity).
            Defaults to 5.
        verbose (bool, optional): If True, prints the applied effect details.
            Defaults to False.

    Returns:
        The blurred image.
    """
    image = _bytes_to_image(image)
    min_kernel_size, max_kernel_size = _validate_range_logic(min_kernel_size, max_kernel_size)
    
    kernel_size = random.randint(min_kernel_size, max_kernel_size)

    # Ensure kernel size is odd, as required by GaussianBlur
    if kernel_size % 2 == 0:
        kernel_size += 1

    if verbose:
        print(f" - Applying Blur with kernel size: {kernel_size}")

    image_array = cv2.GaussianBlur(np.array(image), (kernel_size, kernel_size), 0)
    return Image.fromarray(image_array)

def motion_blur(image: Union[Image.Image, bytes], min_kernel_size: int = 5, max_kernel_size: int = 7, angle: float = None, verbose: bool = False) -> Image.Image:
    """
    Applies motion blur to simulate shaky hands.

    Creates a linear kernel in a random direction if not specified.

    Args:
        image (Image.Image or bytes): The input image.
        min_kernel_size (int, optional): Minimum kernel size (blur intensity).
            Defaults to 5.
        max_kernel_size (int, optional): Maximum kernel size (blur intensity).
            Defaults to 7.
        angle (float, optional): Angle of motion in degrees. If None, random.
            Defaults to None.
        verbose (bool, optional): If True, prints the applied effect details.
            Defaults to False.
    Returns:
        Image.Image: The image with motion blur.
    """
    image = _bytes_to_image(image)
    min_kernel_size, max_kernel_size = _validate_range_logic(min_kernel_size, max_kernel_size)

    image_array = np.array(image)

    if angle is None:
        angle = random.uniform(0, 360)

    kernel_size = random.randint(min_kernel_size, max_kernel_size)

    if verbose:
        print(f" - Applying Motion Blur with kernel_size={kernel_size}, angle={angle:.2f} degrees")
        
    # Create a motion blur kernel.
    kernel = np.zeros((kernel_size, kernel_size))
    kernel[kernel_size // 2] = np.ones(kernel_size) / kernel_size
    M = cv2.getRotationMatrix2D((kernel_size / 2 - 0.5, kernel_size / 2 - 0.5), angle, 1)
    kernel = cv2.warpAffine(kernel, M, (kernel_size, kernel_size))
    
    # Apply the kernel to each channel.
    blurred = cv2.filter2D(image_array, -1, kernel)
    return Image.fromarray(blurred)

def add_noise(image: Union[Image.Image, bytes], min_std: float = 2, max_std: float = 8, verbose: bool = False) -> Image.Image:
    """
    Adds Gaussian noise to the image to simulate sensor noise.

    Args:
        image (Image.Image or bytes): The input image.
        min_std (float, optional): The minumun value for the standard
            deviation of the noise
        max_std (float, optional): The maximun value for the standard
            deviation of the noise
        verbose (bool, optional): If True, prints the applied effect details.
            Defaults to False.        

    Returns:
        The image with added noise.
    """
    image = _bytes_to_image(image)
    low, high = _validate_range_logic(min_std, max_std)

    image_array = np.array(image).astype(np.float32)

    std = random.uniform(low, high)
    
    if verbose:
        print(f" - Applying Noise with standard deviation: {std:.2f}")

    noise = np.random.normal(0, std, image_array.shape)

    image_array = np.clip(image_array + noise, 0, 255)
    return Image.fromarray(image_array.astype(np.uint8))

def over_sharpening(image: Union[Image.Image, bytes], radius: float = 2.0, percent: int = 150, threshold: int = 3, verbose: bool = False) -> Image.Image:
    """
    Applies aggressive over-sharpening to simulate phone processing that tries to 'enhance' sharpness.

    Args:
        image (Image.Image or bytes): The input image.
        radius (float, optional): Radius of the mask. Defaults to 2.0.
        percent (int, optional): Sharpening percentage. Defaults to 150.
        threshold (int, optional): Threshold to apply. Defaults to 3.
        verbose (bool, optional): If True, prints the applied effect details. Defaults to False.

    Returns:
        Image.Image: The over-sharpened image.
    """
    image = _bytes_to_image(image)
    
    if verbose:
        print(f" - Applying Over-Sharpening with radius={radius}, percent={percent}, threshold={threshold}")

    return image.filter(ImageFilter.UnsharpMask(radius=radius, percent=percent, threshold=threshold))
