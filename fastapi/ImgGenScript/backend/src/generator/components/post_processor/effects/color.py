import cv2
import random
import numpy as np

from PIL import Image, ImageEnhance
from typing import Union

from ..utils.utils import _validate_range_logic, _bytes_to_image

def hdr_simulation(image: Union[Image.Image, bytes], exposure: float = 1.0, local_contrast: bool = True, tone_map_strength: float = 1.0, verbose: bool = False) -> Image.Image:
    """ 
    Simulates an HDR effect by expanding the dynamic range, recovering details in shadows and highlights.

    Uses exposure correction, adaptive equalization, and a simple tone mapping operator (Reinhard-like).

    Args:
        image (Image.Image or bytes): The input image.
        exposure (float, optional): Exposure factor for brightening shadows. Defaults to 1.0.
        local_contrast (bool, optional): If True, applies CLAHE for local contrast. Defaults to True.
        tone_map_strength (float, optional): Intensity of the tone mapping (0-2). Defaults to 1.0.
        verbose (bool, optional): If True, prints the applied effect details. Defaults to False.

    Returns:
        Image.Image: The image with HDR simulation.
    """ 
    image = _bytes_to_image(image)

    if verbose:
        print(f" - Applying HDR Simulation with exposure={exposure}, local_contrast={local_contrast}, tone_map_strength={tone_map_strength}")
    image_array = np.array(image).astype(np.float32) / 255.0
    
    # Exposure adjustment to recover shadow details.
    image_array *= exposure
    image_array = np.clip(image_array, 0, 1)
    
    # Simple Reinhard-like tone mapping to compress highlights while preserving details.
    luminance = np.mean(image_array, axis=2)
    L_white = 1.0

    tone_mapped = (luminance * (1 + luminance / (L_white ** 2))) / (1 + luminance)
    for c in range(3):
        image_array[:, :, c] = image_array[:, :, c] * tone_mapped / (luminance + 1e-6) * tone_map_strength
    
    image_array = np.clip(image_array, 0, 1)
    
    # Apply local contrast enhancement (CLAHE) to simulate merged exposures.
    if local_contrast:
        lab = cv2.cvtColor((image_array * 255).astype(np.uint8), cv2.COLOR_RGB2LAB)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        lab[:, :, 0] = clahe.apply(lab[:, :, 0])
        image_array = cv2.cvtColor(lab, cv2.COLOR_LAB2RGB) / 255.0
    
    return Image.fromarray((image_array * 255).astype(np.uint8))

def sdr_simulation(image: Union[Image.Image, bytes], gamma: float = 0.9, contrast: float = 1.3, clip_threshold: float = 0.05, verbose: bool = False) -> Image.Image:
    """
    Simulates a limited Standard Dynamic Range (SDR), typical of basic phone sensors.

    Crushes shadows and blows out highlights, with clipping at the extremes.

    Args:
        image (Image.Image or bytes): The input image.
        gamma (float, optional): Gamma factor to crush shadows. Defaults to 0.9.
        contrast (float, optional): Contrast factor to blow out highlights. Defaults to 1.3.
        clip_threshold (float, optional): Clipping threshold (0-0.5). Defaults to 0.05.
        verbose (bool, optional): If True, prints the applied effect details. Defaults to False.

    Returns:
        Image.Image: The image with SDR simulation.
    """
    image = _bytes_to_image(image)

    if verbose:
        print(f" - Applying SDR Simulation with gamma={gamma}, contrast={contrast}, clip_threshold={clip_threshold}")
    image_array = np.array(image).astype(np.float32) / 255.0
    
    # Crush shadows: gamma < 1 darkens low-intensity values.
    image_array = np.power(image_array, gamma)
    
    # Blow out highlights: contrast boost pushes high values towards white.
    image_array = np.clip((image_array - 0.5) * contrast + 0.5, 0, 1)
    
    # Hard clip the extremes to simulate sensor banding.
    low_mask = image_array < clip_threshold
    high_mask = image_array > (1 - clip_threshold)

    image_array[low_mask] = 0
    image_array[high_mask] = 1
    
    return Image.fromarray((image_array * 255).astype(np.uint8))

def limited_dynamic_range(image: Union[Image.Image, bytes], gamma: float = 0.9, contrast: float = 1.3, verbose: bool = False) -> Image.Image:
    """
    Simulates the limited dynamic range of a typical phone sensor.

    This effect crushes shadows and blows out highlights slightly.

    Args:
        image (Image.Image or bytes): The input image.
        gamma (float, optional): Gamma correction factor. Defaults to 0.9.
        contrast (float, optional): Contrast enhancement factor. Defaults to 1.3.
        verbose (bool, optional): If True, prints the applied effect details. Defaults to False.

    Returns:
        The image with simulated low dynamic range.
    """
    image = _bytes_to_image(image)
    if verbose:
        print(f" - Applying Limited Dynamic Range with gamma={gamma}, contrast={contrast}")

    image_array = np.array(image).astype(np.float32) / 255.0
    image_array = np.power(image_array, gamma)

    image_array = np.clip((image_array - 0.5) * contrast + 0.5, 0, 1)
    return Image.fromarray((image_array * 255).astype(np.uint8))

def random_contrast(image: Union[Image.Image, bytes], low: float = 0.8, high: float = 1.2, verbose: bool = False) -> Image.Image:
    """
    Applies a random contrast adjustment to the image.

    Args:
        image (Image.Image or bytes): The input image.
        low (float, optional): The minimum contrast factor. Defaults to 0.8.
        high (float, optional): The maximum contrast factor. Defaults to 1.2.
        verbose (bool, optional): If True, prints the applied effect details. Defaults to False.

    Returns:
        The image with adjusted contrast.
    """
    image = _bytes_to_image(image)
    low, high = _validate_range_logic(low, high)

    factor = random.uniform(low, high)
    
    if verbose:
        print(f" - Applying Contrast with factor: {factor:.2f}")

    return ImageEnhance.Contrast(image).enhance(factor)

def random_saturation(image: Union[Image.Image, bytes], low: float = 0.8, high: float = 1.2, verbose: bool = False) -> Image.Image:
    """
    Applies a random saturation adjustment to the image.

    Args:
        image (Image.Image or bytes): The input image.
        low (float, optional): The minimum saturation factor. Defaults to 0.8.
        high (float, optional): The maximum saturation factor. Defaults to 1.2.
        verbose (bool, optional): If True, prints the applied effect details. Defaults to False.

    Returns:
        The image with adjusted saturation.
    """
    image = _bytes_to_image(image)
    low, high = _validate_range_logic(low, high)

    factor = random.uniform(low, high)
    
    if verbose:
        print(f" - Applying Saturation with factor: {factor:.2f}")

    return ImageEnhance.Color(image).enhance(factor)

def random_tint(image: Union[Image.Image, bytes], light_temp: str = "neutral", intensity: float = 10, verbose: bool = False) -> Image.Image:
    """
    Applies a random color tint to the image.

    The tint can be biased towards a certain color temperature.

    Args:
        image (Image.Image or bytes): The input image.
        light_temp (str, optional): The lighting temperature to simulate.
            Options: "warm", "neutral", "cool". Defaults to "neutral".
        intensity (float, optional): The maximum magnitude of the RGB color shift.
            Higher values result in a stronger tint. Defaults to 10.
        verbose (bool, optional): If True, prints the applied effect details. Defaults to False.

    Returns:
        The tinted image.
    """
    image = _bytes_to_image(image)
    image_array = np.array(image).astype(np.float32)

    if light_temp == "warm":
        # Bias toward reds/yellows (avoid cold blues)
        r_shift = np.random.uniform(0, intensity)
        g_shift = np.random.uniform(0, intensity * 0.5)
        b_shift = np.random.uniform(-intensity * 0.3, 0)
    elif light_temp == "cool":
        # Bias toward blues/cyans
        r_shift = np.random.uniform(-intensity * 0.4, 0)
        g_shift = np.random.uniform(0, intensity * 0.5)
        b_shift = np.random.uniform(0, intensity)
    elif light_temp == "neutral":
        # Fully random shifts for a neutral temperature.
        r_shift, g_shift, b_shift = np.random.uniform(-intensity * 0.25, intensity * 0.25, size=3)
        # g_shift *= 0.5
    else:
        raise ValueError("light_temp must be 'warm', 'neutral', or 'cool'.")

    shift = np.array([r_shift, g_shift, b_shift])

    if verbose:
        print(f" - Applying Tint: (R:{r_shift:.2f}, G:{g_shift:.2f}, B:{b_shift:.2f})")

    image_array = np.clip(image_array + shift, 0, 255)
    return Image.fromarray(image_array.astype(np.uint8))