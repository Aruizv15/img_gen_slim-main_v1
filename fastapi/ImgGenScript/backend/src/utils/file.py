import os
import re
import logging
import shutil
import hashlib
from datetime import datetime
from typing import List, Optional, Tuple

def ensure_dir(path: str) -> None:
    """
    Ensures that a directory exists, creating it if necessary.

    Args:
        path (str): The file system path of the directory to check and create.
    """
    os.makedirs(path, exist_ok=True)


def clear_directory_contents(directory_path: str, logger: logging.Logger = None) -> None:
    """
    Removes all files and subdirectories from within a given directory.

    This function iterates through all items in the specified directory and
    deletes them, leaving the directory itself empty. It does not delete
    the directory itself.

    Args:
        directory_path (str): The path to the directory whose contents will be cleared.
        logger (logging.Logger, optional): A logger instance for recording errors
            or warnings. Defaults to None.
    """
    if not os.path.isdir(directory_path):
        if logger:
            logger.warning(f"Warning: Directory does not exist for clearing: {directory_path}")
        return

    for item in os.listdir(directory_path):
        item_path = os.path.join(directory_path, item)
        try:
            if os.path.isfile(item_path) or os.path.islink(item_path):
                os.unlink(item_path)
            elif os.path.isdir(item_path):
                shutil.rmtree(item_path)
        except Exception as e:
            if logger:
                logger.error(f"Failed to delete {item_path}. Reason: {e}", exc_info=True)


def find_project_dirs(base_path: str, logger: logging.Logger = None) -> List[str]:
    """
    Finds all subdirectories that match the 'OVODxxxxx' naming pattern.

    This function scans a base directory for subdirectories whose names
    match the regular expression `OVOD\\d{5}` (e.g., 'OVOD00001').

    Args:
        base_path (str): The root directory to search within.
        logger (logging.Logger, optional): A logger instance for recording errors
            or warnings. Defaults to None.

    Returns:
        List[str]: A sorted list of absolute paths to the matching project directories.
    """
    project_dirs: List[str] = []
    if not os.path.isdir(base_path):
        if logger:
            logger.warning(f"Warning: Project base directory not found: {base_path}")
        return []

    try:
        for entry in os.listdir(base_path):
            full_path = os.path.join(base_path, entry)
            if os.path.isdir(full_path) and re.fullmatch(r'OVOD\d{5}', entry):
                project_dirs.append(full_path)
    except Exception as e:
        if logger:
            logger.error(f"An unexpected error occurred while listing directory {base_path}: {e}", exc_info=True)
        return []

    project_dirs.sort()
    return project_dirs


def copy_images_to_folder(source_folder: str, destination_folder: str, logger: logging.Logger = None) -> None:
    """
    Copies all image files from a source folder to a destination folder.

    Args:
        source_folder (str): The path to the folder containing the images to copy.
        destination_folder (str): The path to the folder where images will be copied.
        logger (logging.Logger, optional): A logger instance for recording progress
            and errors. Defaults to None.

    Raises:
        FileNotFoundError: If the source folder does not exist.
        IOError: If creating the destination directory or copying a file fails.
    """
    if not os.path.isdir(source_folder):
        raise FileNotFoundError(f"Source folder does not exist: {source_folder}")

    try:
        os.makedirs(destination_folder, exist_ok=True)
    except Exception as e:
        if logger:
            logger.error(f"Error creating destination directory {destination_folder}: {e}", exc_info=True)
        raise IOError(f"Failed to create destination directory {destination_folder}: {e}")

    image_extensions = ('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp')

    for filename in os.listdir(source_folder):
        file_path = os.path.join(source_folder, filename)

        if os.path.isfile(file_path) and filename.lower().endswith(image_extensions):
            destination_path = os.path.join(destination_folder, filename)
            try:
                shutil.copy2(file_path, destination_path)
                if logger:
                    logger.debug(f"Copied: {filename} to {destination_folder}")
            except PermissionError as e:
                if logger:
                    logger.error(f"Permission error copying {filename} to {destination_folder}: {e}", exc_info=True)
                raise
            except Exception as e:
                if logger:
                    logger.error(f"Error copying {filename} to {destination_folder}: {e}", exc_info=True)
                raise IOError(f"Unknown error copying {filename}: {e}")


def copy_image_to_folder(source_image_path: str, destination_folder: str, logger: logging.Logger = None) -> None:
    """
    Copies a single image file to a destination folder.

    Args:
        source_image_path (str): The full path to the image file to copy.
        destination_folder (str): The path to the folder where the image will be copied.
        logger (logging.Logger, optional): A logger instance for recording progress
            and errors. Defaults to None.

    Raises:
        FileNotFoundError: If the source image does not exist.
        ValueError: If the source file is not a recognized image type.
        IOError: If creating the destination directory or copying the file fails.
    """
    if not os.path.isfile(source_image_path):
        raise FileNotFoundError(f"Source image does not exist or is not a file: {source_image_path}")

    filename = os.path.basename(source_image_path)
    image_extensions = ('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp')

    if not filename.lower().endswith(image_extensions):
        raise ValueError(f"File '{filename}' does not have a recognized image extension.")

    try:
        os.makedirs(destination_folder, exist_ok=True)
    except Exception as e:
        if logger:
            logger.error(f"Error creating destination directory {destination_folder}: {e}", exc_info=True)
        raise IOError(f"Failed to create destination directory {destination_folder}: {e}")

    destination_path = os.path.join(destination_folder, filename)

    try:
        shutil.copy2(source_image_path, destination_path)
        if logger:
            logger.debug(f"Copied: '{filename}' to '{destination_folder}'")
    except PermissionError as e:
        if logger:
            logger.error(f"Permission error copying '{filename}' to '{destination_folder}': {e}", exc_info=True)
        raise
    except Exception as e:
        if logger:
            logger.error(f"Error copying '{filename}' to '{destination_folder}': {e}", exc_info=True)
        raise IOError(f"Unknown error copying '{filename}': {e}")

def save_generated_images(generated_images: List[Tuple[str, bytes]], output_dir: str, suffix: str = "", logger: logging.Logger = None) -> None:
    """
    Saves a list of in-memory images to disk with a timestamp prefix and an optional suffix.

    Each image is saved with a unique filename generated by prepending a
    timestamp and inserting a suffix before the file extension.

    Args:
        generated_images (List[Tuple[str, bytes]]): A list of tuples, where each
            tuple contains an original filename and the image data as bytes.
        output_dir (str): The directory where the images will be saved.
        suffix (str, optional): A suffix to add to the filename before the
            extension (e.g., '_raw'). Defaults to "".
        logger (logging.Logger, optional): A logger instance for recording progress
            and errors. Defaults to None.
    """
    for filename, image_bytes in generated_images:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        base_name, ext = os.path.splitext(filename)
        
        filename = f"{base_name}_{suffix}{ext}"
        unique_filename = f"{timestamp}_{filename}".replace("__", "_")
        file_path = os.path.join(output_dir, unique_filename)

        try:
            os.makedirs(output_dir, exist_ok=True)
            with open(file_path, "wb") as f:
                f.write(image_bytes)
            if logger:
                logger.debug(f"Saved image: {file_path}")
        except IOError as e:
            if logger:
                logger.error(f"Error saving image {filename}: {e}")
        except Exception as e:
            if logger:
                logger.error(f"An unexpected error occurred while saving image {filename}: {e}")
                
def move_and_rename_generated_images(
        generated_images_info: List[Tuple[str, str]],
        output_dir: str,
        destination_dir: str,
        logger: logging.Logger = None
    ) -> None:
    """
    Moves and renames generated images from an output directory to a destination.

    Args:
        generated_images_info (List[Tuple[str, str]]): A list of tuples, where each
            tuple contains a filename and its original subfolder.
        output_dir (str): The path to the ComfyUI output directory where images are stored.
        destination_dir (str): The final directory where images will be moved.
        logger (logging.Logger, optional): A logger instance for recording progress
            and errors. Defaults to None.
    """
    for filename, subfolder in generated_images_info:
        source_path = os.path.join(output_dir, filename)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_filename = f"{timestamp}_{filename}"
        destination_path = os.path.join(destination_dir, unique_filename)

        try:
            if os.path.exists(source_path):
                shutil.move(source_path, destination_path)
                if logger:
                    logger.debug(f"Moved {filename} to {destination_path}")
            else:
                if logger:
                    logger.warning(f"Warning: Generated image {source_path} not found.")
        except Exception as e:
            if logger:
                logger.error(f"Error moving image {filename} from {source_path} to {destination_path}: {e}", exc_info=True)

def files_are_identical(src: str, dst: str, block_size: int = 8192) -> bool:
    """
    Compare two files by content using MD5 hash.

    Args:
        src (str): Path to the source file.
        dst (str): Path to the destination file.
        block_size (int): Size of blocks to read (default 8KB).

    Returns:
        bool: True if files are identical, False otherwise.
    """
    hash_src = hashlib.md5()
    hash_dst = hashlib.md5()

    try:
        with open(src, 'rb') as f_src, open(dst, 'rb') as f_dst:
            while chunk := f_src.read(block_size):
                hash_src.update(chunk)
            while chunk := f_dst.read(block_size):
                hash_dst.update(chunk)
        return hash_src.hexdigest() == hash_dst.hexdigest()
    except (OSError, IOError) as e:
        return False
                
def organize_approved_images(
    images_dir: str,
    approved_dir: str,
    logger: Optional[logging.Logger] = None,
    check_content: bool = False
) -> None:
    """
    Scans project folders for 'OK' images and copies them to an approved directory.
    Skips copying if the image already exists (by name or optionally by content).

    This function walks through project folders (e.g., 'OVODxxxxx'), finds
    images within 'fullbody' or 'portrait' subfolders that contain "OK" in
    their filename, and copies them to a mirrored directory structure inside
    the specified `approved_dir`.

    - If `check_content=False` (default): skips if file with same name exists.
    - If `check_content=True`: skips only if file exists AND has identical content.

    Args:
        images_dir (str): The root directory containing the project folders to scan.
        approved_dir (str): The root directory where approved images will be copied.
        logger (Optional[logging.Logger], optional): A logger instance for
            recording progress and errors. Defaults to None.
        check_content (bool, optional): If True, compares file content using MD5 hash
            when a file with the same name already exists. Defaults to False.
    """
    os.makedirs(approved_dir, exist_ok=True)

    if not os.path.exists(images_dir):
        if logger:
            logger.error(f"The 'images' folder was not found in '{images_dir}'")
        return

    for entry in os.listdir(images_dir):
        donor_path = os.path.join(images_dir, entry)

        if os.path.isdir(donor_path) and re.fullmatch(r'OVOD\d{5}', entry):
            if logger:
                logger.info(f"Reviewing project: {entry}")

            for subfolder_name in ["fullbody", "portrait"]:
                subfolder_path = os.path.join(donor_path, subfolder_name)

                if os.path.isdir(subfolder_path):
                    for image_name in os.listdir(subfolder_path):
                        # Check for "OK" as a whole word or part of the name, case-insensitive
                        if "OK" in image_name.upper():
                            source_image_path = os.path.join(subfolder_path, image_name)

                            dest_project_dir = os.path.join(approved_dir, entry)
                            dest_subfolder_dir = os.path.join(dest_project_dir, subfolder_name)
                            destination_image_path = os.path.join(dest_subfolder_dir, image_name)

                            # Create destination directory if it doesn't exist
                            os.makedirs(dest_subfolder_dir, exist_ok=True)

                            # Skip if file already exists
                            if os.path.exists(destination_image_path):
                                if check_content:
                                    if files_are_identical(source_image_path, destination_image_path):
                                        if logger:
                                            logger.debug(f"Skipped (identical content): {destination_image_path}")
                                        continue
                                    else:
                                        if logger:
                                            logger.warning(f"Overwriting different file with same name: {destination_image_path}")
                                else:
                                    if logger:
                                        logger.debug(f"Skipped (already exists): {destination_image_path}")
                                    continue

                            # Copy the file
                            try:
                                shutil.copy2(source_image_path, destination_image_path)
                                if logger:
                                    action = "Copied" if not os.path.exists(destination_image_path) or not check_content else "Overwritten"
                                    logger.info(f"{action}: {image_name} → {dest_subfolder_dir}")
                            except IOError as e:
                                if logger:
                                    logger.error(f"Error copying {image_name}: {e}", exc_info=True)
                else:
                    if logger:
                        logger.debug(f"Subfolder '{subfolder_name}' not found in '{entry}', skipping.")