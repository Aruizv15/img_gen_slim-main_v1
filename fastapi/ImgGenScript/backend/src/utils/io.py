import os
import csv
import json
import yaml
import logging

from typing import List, Optional, Dict, Any

def load_json_file(file_path: str, logger: Optional[logging.Logger] = None) -> Any:
    """
    Loads a JSON file from the specified path.

    This function safely opens and parses a JSON file. If the file is not found
    or contains invalid JSON, it logs an error (if a logger is provided) and
    re-raises the original exception.

    Args:
        file_path (str): The path to the JSON file.
        logger (logging.Logger, optional): A logger instance for recording errors.
            Defaults to None.

    Returns:
        Any: The parsed content of the JSON file.

    Raises:
        FileNotFoundError: If the file is not found at the specified path.
        json.JSONDecodeError: If the file content is not valid JSON.
        Exception: For other unexpected errors during file reading.
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError as e:
        if logger:
            logger.error(f"Error: File not found at {file_path}")
        raise e
    except json.JSONDecodeError as e:
        if logger:
            logger.error(f"Error: Could not decode JSON from {file_path}. Please check the file format.")
        raise e
    except Exception as e:
        if logger:
            logger.error(f"An unexpected error occurred while loading {file_path}: {e}", exc_info=True)
        raise e

def save_json_file(file_path: str, data: Any, indent: int = 4, logger: Optional[logging.Logger] = None) -> None:
    """
    Saves data to a file in JSON format.

    This function safely serializes a Python object and writes it to a JSON file.
    If an error occurs during file writing or serialization, it logs an error
    (if a logger is provided) and re-raises the original exception.

    Args:
        file_path (str): The path where the JSON file will be saved.
        data (Any): The Python object to serialize to JSON.
        indent (int, optional): The indentation level for pretty-printing. Defaults to 4.
        logger (logging.Logger, optional): A logger for recording errors. Defaults to None.

    Raises:
        IOError: If an error occurs while writing to the file.
        TypeError: If the data cannot be serialized to JSON.
        Exception: For other unexpected errors during file writing.
    """
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=indent, ensure_ascii=False)
    except (IOError, TypeError) as e:
        if logger:
            logger.error(f"Error saving JSON to {file_path}: {e}", exc_info=True)
        raise e
    except Exception as e:
        if logger:
            logger.error(f"An unexpected error occurred while saving {file_path}: {e}", exc_info=True)
        raise e


def load_text_file(file_path: str, logger: logging.Logger = None) -> str:
    """
    Loads the content of a text file into a single string.

    This function reads an entire text file, strips leading/trailing whitespace,
    and returns its content. If the file cannot be found or read, it logs an
    error and returns an empty string.

    Args:
        file_path (str): The path to the text file.
        logger (logging.Logger, optional): A logger instance for recording errors.
            Defaults to None.

    Returns:
        str: The content of the text file, or an empty string if an error occurs.
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read().strip()
    except FileNotFoundError:
        if logger:
            logger.error(f"Error: Text file not found at {file_path}")
        return ""
    except Exception as e:
        if logger:
            logger.error(f"An unexpected error occurred while loading {file_path}: {e}", exc_info=True)
        return ""


def load_csv_data(file_path: str, logger: logging.Logger = None) -> List[Dict]:
    """
    Loads data from a CSV file into a list of dictionaries.

    This function reads a semicolon-delimited CSV file where the first row is
    assumed to be the header. Each subsequent row is converted into a dictionary
    mapping header names to cell values. It uses 'utf-8-sig' encoding to handle
    potential Byte Order Marks (BOM).

    Args:
        file_path (str): The path to the CSV file.
        logger (logging.Logger, optional): A logger instance for recording errors.
            Defaults to None.

    Returns:
    """
    data: List[Dict] = []
    try:
        with open(file_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f, delimiter=';')
            data = list(reader)
    except FileNotFoundError:
        if logger:
            logger.error(f"Error: CSV file not found at {file_path}")
    except Exception as e:
        if logger:
            logger.error(f"Error reading CSV file {file_path}: {e}", exc_info=True)
    return data

def load_yaml_file(path: str):
    """
    This function reads a YAML or YML file from the specified path, performing several checks
    to ensure the file exists and has a valid extension. The file's content is then safely
    parsed into a Python object (e.g., a dictionary or list).

    Args:
        path (str): The full path to the YAML file.

    Raises:
        TypeError: If the provided path is not a string.
        FileNotFoundError: If the file does not exist at the specified path.
        ValueError: If the file does not have a .yaml or .yml extension, or if there is a parsing error.
            a parsing error occurs.
    """
    if not isinstance(path, str):
        raise TypeError("The 'path' argument must be a string.")
    if not os.path.exists(path):
        raise FileNotFoundError(f"The file '{path}' does not exist.")
    if not path.lower().endswith((".yaml", ".yml")):
        raise ValueError("The file must have a .yaml or .yml extension.")
    
    with open(path, "r", encoding="utf-8") as file:
        try:
            content = yaml.safe_load(file)
            return content
        except yaml.YAMLError as e:
            raise ValueError(f"Error parsing YAML file '{path}': {e}")

def write_last_processed_project(dir_path: str, file_name: str, project_name: str, logger: logging.Logger = None) -> None:
    """
    This function is used to persist the state of a batch run, allowing it to
    be resumed later. It creates or overwrites a file with the name of the
    project that is about to be processed.

    Args:
        dir_path (str): Directory where the state file will be written.
        file_name (str): The name of the file to store the project name in.
        project_name (str): The project identifier to write (e.g., 'OVOD00001').
        logger (logging.Logger, optional): A logger instance to use for messages.
            Defaults to None.
    """
    try:
        os.makedirs(dir_path, exist_ok=True)
        file_path = os.path.join(dir_path, file_name)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(project_name)
        if logger:
            logger.debug(f"Saved last processed project: {project_name}")
    except Exception as e:
        if logger:
            logger.error(f"Error writing last processed project file {file_path}: {e}", exc_info=True)

def read_last_processed_project(dir_path: str, file_name: str, logger: logging.Logger = None) -> Optional[str]:
    """
    This function is used to resume a batch run by retrieving the name of the
    last project that was being processed before the run was interrupted.

    Args:
        dir_path (str): Directory where the state file is expected.
        file_name (str): The name of the file that stores the project name.
        logger (logging.Logger, optional): A logger instance for recording progress
            and errors. Defaults to None.

    Returns:
        str | None: The project name if found and non-empty, otherwise None.
            otherwise None.
    """
    file_path = os.path.join(dir_path, file_name)
    if not os.path.exists(file_path):
        return None
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            project_name = f.read().strip()
            if project_name:
                if logger:
                    logger.info(f"Resuming from last processed project: {project_name}")
                return project_name
    except Exception as e:
        if logger:
            logger.error(f"Error reading last processed project file {file_path}: {e}", exc_info=True)
    return None

def clear_last_processed_project(dir_path: str, file_name: str, logger: logging.Logger = None) -> None:
    """
    This function is called at the end of a successful batch cycle to clean up
    the state file, ensuring the next run starts from the beginning.

    Args:
        dir_path (str): Directory where the state file is stored.
        file_name (str): The name of the state file to delete.
        logger (logging.Logger, optional): A logger instance for recording progress
            and errors. Defaults to None.
    """
    file_path = os.path.join(dir_path, file_name)
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
            if logger:
                logger.info("Cleared last processed project state.")
        except Exception as e:
            if logger:
                logger.error(f"Error deleting last processed project file {file_path}: {e}", exc_info=True)