import sys
import logging
from pathlib import Path
from typing import Optional

from backend.src.config.settings import get_settings

settings = get_settings()

class StandardFormatter(logging.Formatter):
    def __init__(self):
        super().__init__(
            fmt=settings.log_format,
            datefmt="%Y-%m-%d %H:%M:%S",
        )


def get_logger(
    name: str,
    *,
    log_file: Optional[Path | str] = None,
    level: Optional[str] = None,
) -> logging.Logger:
    """
    Returns a configured and reusable logger instance.

    This function sets up a logger with a standard format that logs to both the
    console and an optional file. It prevents adding duplicate handlers if the
    logger has already been configured, making it safe for hot-reloading environments.

    Args:
        name (str): The name for the logger, typically `__name__`.
        log_file (Optional[Path | str]): An optional path to a specific log file (e.g., "generation.log").
        level (Optional[str]): The logging level. If not provided, the level from settings is used.

    Returns:
        logging.Logger: A fully configured logger instance.
    """
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger

    log_level = getattr(logging, (level or settings.log_level).upper(), logging.INFO)
    logger.setLevel(log_level)

    # Console handler (stdout)
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(log_level)
    console.setFormatter(StandardFormatter())
    logger.addHandler(console)

    if log_file:
        log_file_path = Path(log_file)
        log_file_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.FileHandler(log_file_path)
        file_handler.setLevel(log_level)
        file_handler.setFormatter(StandardFormatter())
        logger.addHandler(file_handler)

    logger.propagate = False
    return logger

def get_generation_logger() -> logging.Logger:
    """
    Gets a specific logger for the batch generation processes.

    This logger is pre-configured to always write to `<log_dir>/generation.log`,
    centralizing all batch generation logs into a single file.
    """
    log_path = Path(settings.log_dir) / "generation.log"
    return get_logger("ImgGen", log_file=log_path, level=settings.log_level)