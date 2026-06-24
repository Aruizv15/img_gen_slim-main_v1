import cv2
import random
import numpy as np

from PIL import Image, ImageFilter, ImageDraw
from typing import Union

from ..utils.utils import _validate_range_logic, _bytes_to_image

def lens_distortion(image: Union[Image.Image, bytes], strength: float = 0.2, verbose: bool = False) -> Image.Image:
    """
    Simulates barrel lens distortion with automatic zoom to eliminate black borders.

    Args:
        image (Image.Image or bytes): The input image.
        strength (float, optional): The strength of the barrel distortion.
            Higher values create a more pronounced effect. Defaults to 0.2.
        verbose (bool, optional): If True, prints the applied effect details. Defaults to False.

    Returns:
        The image with lens distortion applied.
    """
    image = _bytes_to_image(image)

    if verbose:
        print(f" - Applying Lens Distortion with strength: {strength:.3f}")
        
    image_array = np.array(image)
    h, w = image_array.shape[:2]

    # Simplified camera matrix assuming focal length is the max dimension.
    f = max(w, h)
    cx, cy = w / 2, h / 2
    camera_matrix = np.array([[f, 0, cx], [0, f, cy], [0, 0, 1]], dtype=np.float32)

    # Distortion coefficients (k1, k2, p1, p2, k3). Only barrel (k1) is used.
    dist_coeffs = np.array([strength, 0, 0, 0, 0], dtype=np.float32)

    # Compute optimal new camera matrix for automatic zoom (alpha=0 ensures no black pixels).
    new_camera_matrix, _ = cv2.getOptimalNewCameraMatrix(camera_matrix, dist_coeffs, (w, h), alpha=0)

    # Apply the undistortion with the new matrix to crop and zoom automatically.
    return Image.fromarray(cv2.undistort(image_array, camera_matrix, dist_coeffs, None, new_camera_matrix))

def chromatic_aberration(image: Union[Image.Image, bytes], strength: int = 1, verbose: bool = False) -> Image.Image:
    """
    Simulates chromatic aberration by slightly shifting the R and B color channels.

    Args:
        image (Image.Image or bytes): The input image.
        strength (int, optional): The maximum pixel shift for the channels.
            A higher value creates a more noticeable effect. Defaults to 1.
        verbose (bool, optional): If True, prints the applied effect details. Defaults to False.

    Returns:
        The image with simulated chromatic aberration.
    """
    image = _bytes_to_image(image)

    if strength == 0:
        return image 

    image_array = np.array(image)

    h, w = image_array.shape[:2]

    # Define small, random horizontal and vertical shifts for R and B channels.
    r_dx, r_dy = 0, 0
    while r_dx == 0 and r_dy == 0:
        r_dx, r_dy = random.randint(-strength, strength), random.randint(-strength, strength)
    b_dx, b_dy = 0, 0
    while b_dx == 0 and b_dy == 0:
        b_dx, b_dy = random.randint(-strength, strength), random.randint(-strength, strength)

    if verbose:
        print(f" - Applying Chromatic Aberration with strength: {strength} and shifts: R: {r_dx}, {r_dy} | B: {b_dx}, {b_dy}")
        
    # Create translation matrices for the affine transformation.
    M_r = np.float32([[1, 0, r_dx], [0, 1, r_dy]])
    M_b = np.float32([[1, 0, b_dx], [0, 1, b_dy]])

    # Apply the affine warp to shift the R and B channels independently.
    r_channel = cv2.warpAffine(image_array[:,:,0], M_r, (w, h))
    g_channel = image_array[:,:,1] # Green channel remains stationary
    b_channel = cv2.warpAffine(image_array[:,:,2], M_b, (w, h))

    return Image.fromarray(np.stack([r_channel, g_channel, b_channel], axis=2))

def vignette(image: Union[Image.Image, bytes], low: float = 0.1, high: float = 0.4, verbose: bool = False) -> Image.Image:
    """
    Applies a vignette effect, darkening the corners of the image.

    Args:
        image (Image.Image): The input image.
        low (float, optional): The minimum strength of the vignette effect.
            Defaults to 0.1.
        high (float, optional): The maximum strength of the vignette effect.
            Defaults to 0.4.
        verbose (bool, optional): If True, prints the applied effect details. Defaults to False.

    Returns:
        The image with the vignette effect.
    """
    image = _bytes_to_image(image)
    low, high = _validate_range_logic(low, high)
    
    strength = random.uniform(low, high)

    if verbose:
        print(f" - Applying Vignette with strength: {strength:.2f}")
        
    image_array = np.array(image).astype(np.float32) / 255

    h, w = image_array.shape[:2]
    y, x = np.ogrid[:h, :w]

    cx, cy = w / 2, h / 2
    r = np.sqrt((x - cx) ** 2 + (y - cy) ** 2)
    mask = 1 - strength * (r / r.max()) ** 2

    image_array *= mask[..., np.newaxis]

    return Image.fromarray((np.clip(image_array, 0, 1) * 255).astype(np.uint8))

def lens_dust_spots(image: Union[Image.Image, bytes], num_spots: int = 5, max_size: int = 20, opacity: float = 0.3, verbose: bool = False) -> Image.Image:
    """
    Adds dust or spots on the lens: random dark blurred circles.

    Args:
        image (Image.Image or bytes): The input image.
        num_spots (int, optional): Number of spots. Defaults to 5.
        max_size (int, optional): Maximum size of the spots. Defaults to 20.
        opacity (float, optional): Opacity of the spots (0-1). Defaults to 0.3.
        verbose (bool, optional): If True, prints the applied effect details. Defaults to False.

    Returns:
        Image.Image: The image with spots.
    """
    image = _bytes_to_image(image).convert('RGBA')

    w, h = image.size

    num_spots = random.randint(num_spots//2, num_spots)

    if verbose:
        print(f" - Applying Lens Dust Spots: {num_spots} spots, max_size={max_size}, opacity={opacity}")
        
    spot_layer = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(spot_layer)
    
    base_color_rgb = (255, 255, 255)

    for _ in range(num_spots):
        x = random.randint(0, w)
        y = random.randint(0, h)
        size = random.randint(5, max_size)

        min_opacity = opacity * 0.3
        random_opacity = random.uniform(min_opacity, opacity)

        alpha = int(255 * random_opacity) 
        color = (*base_color_rgb, alpha)

        draw.ellipse((x - size, y - size, x + size, y + size), fill=color)

    blur_radius = max(2, max_size / 4)
    blurred_spots = spot_layer.filter(ImageFilter.GaussianBlur(radius=blur_radius))

    image.alpha_composite(blurred_spots)
    
    return image.convert('RGB')

def flash_effect(image: Union[Image.Image, bytes], intensity: float = 0.5, radius: float = 0.7, verbose: bool = False) -> Image.Image:
    """
    Simulates a flash effect: increases brightness in the center and adds glare.

    Creates a radial mask for brightening and clipping highlights.

    Args:
        image (Image.Image or bytes): The input image.
        intensity (float, optional): Flash intensity (0-1). Defaults to 0.5.
        radius (float, optional): Radius of the central effect (0-1). Defaults to 0.7.
        verbose (bool, optional): If True, prints the applied effect details. Defaults to False.

    Returns:
        Image.Image: The image with the flash effect.
    """
    image = _bytes_to_image(image)
    image_array = np.array(image).astype(np.float32) / 255.0

    h, w = image_array.shape[:2]
    y, x = np.ogrid[:h, :w]

    cx, cy = w / 2, h / 2

    dist = np.sqrt((x - cx)**2 + (y - cy)**2) / (max(w, h) / 2)
    mask = np.clip(1 - (dist / radius), 0, 1) ** 2  # Soft radial mask.

    image_array += mask[..., np.newaxis] * intensity
    image_array = np.clip(image_array, 0, 1)  # Clip to simulate blown-out highlights.

    if verbose:
        print(f" - Applying Flash Effect with intensity={intensity:.2f}, radius={radius:.2f}")

    return Image.fromarray((image_array * 255).astype(np.uint8))