import io
from PIL import Image

def resize_image_if_needed(image_path: str, max_dimension: int = 1024) -> bytes:
    """
    Resizes an image if it exceeds a maximum dimension, maintaining aspect ratio.

    This function loads an image from a given path, checks if either its width or
    height exceeds the specified `max_dimension`, and resizes it if necessary.
    The resizing process preserves the original aspect ratio. The final image
    is returned as a bytes object in PNG format.

    Args:
        image_path (str): The path to the image file.
        max_dimension (int, optional): The maximum allowed dimension for the longer
            side of the image. Defaults to 1024.

    Returns:
        bytes: The image data as a bytes object, encoded in PNG format.

    Raises:
        FileNotFoundError: If the file at `image_path` does not exist.
        PIL.UnidentifiedImageError: If the file cannot be opened and identified.
    """
    with Image.open(image_path) as img:
        if img.mode != 'RGB':
            img = img.convert('RGB')

        width, height = img.size

        if width > max_dimension or height > max_dimension:
            if width > height:
                new_width = max_dimension
                new_height = int(height * (max_dimension / width))
            else:
                new_height = max_dimension
                new_width = int(width * (max_dimension / height))
            
            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

        img_byte_arr = io.BytesIO()
        img.save(img_byte_arr, format='PNG')
        return img_byte_arr.getvalue()