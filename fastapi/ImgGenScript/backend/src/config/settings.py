import os
import logging

from typing import Dict, Any, Union, Optional
from pydantic import Field, field_validator, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path

from backend.src.config.fullbody_settings import FullbodySettings
from backend.src.config.portrait_settings import PortraitSettings
from backend.src.utils import load_yaml_file

SENSITIVE_KEYS = {

}

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent

BACKEND_ROOT = BASE_DIR / "backend"
CONFIG_DIR = BACKEND_ROOT / "cfg"
DATA_DIR = BACKEND_ROOT / "data"
LOG_DIR = BACKEND_ROOT / "logs"
PROMPTS_DIR = CONFIG_DIR / "prompts"
WORKFLOW_DIR = CONFIG_DIR / "workflow"
STYLES_DIR = CONFIG_DIR / "styles_data"
FILES_DIR = BASE_DIR / "files"
CSV_DIR = FILES_DIR / "csv"
IMAGES_DIR = FILES_DIR / "images"
REFERECE_FB_DIR = FILES_DIR / "reference" / "fullbody"
REFERECE_PT_DIR = FILES_DIR / "reference" / "portrait"
APPROVED_DIR = FILES_DIR / "approved"

DOTENV_PATH = BASE_DIR / ".env"
CONFIG_PATH = CONFIG_DIR / "config.yaml"

class Settings(BaseSettings):
    """
    Main application settings for batch image generation.

    This class centralizes the configuration for both 'fullbody_batch.py' and
    'portrait_batch.py' scripts, ensuring a single source of truth for all
    common settings. It uses Pydantic's BaseSettings to load values from
    a .env file and environment variables, providing type validation and
    a structured approach to configuration management.

    Features:
        - Centralized configuration management for batch processes.
        - Loads settings from environment variables and a .env file.
        - Provides a method to set up logging dynamically for different scripts.

    Attributes:
        fastapi_server_address (str): The address of the FastAPI server.
        comfyui_server_address (str): The address of the ComfyUI server.
        comfyui_input_dir (str): The ComfyUI input directory inside the container.
        comfyui_reference_dir (str): The reference directory inside the container. 
        comfyui_output_dir (str): The ComfyUI output directory inside the container.
        img_max_dimension (int): The maximum dimension for image resizing.
        max_runs (int): The maximun runs before restart ComfyUI.
        restart_timeout (int): The timeout for restart ComfyUI.
        restart_cooldown (int): The cooldown time after restart ComfyUI.
        max_retries (int): The maximum number of retries for a failed generation.
        retries_delay_seconds (int): The delay in seconds between retries.
        interrupt_after_seconds (int): Time in seconds before an interrupt request is sent.
        interrupt_wait_seconds (int): Time in seconds to wait after an interrupt.
        delay_between_projects (int): The delay in seconds between processing each project.
        delay_between_cycles (int): The delay in seconds between full generation cycles.
        approved_scan_interval (int): The interval in minutes to scan for approved images.
        base_dir (str): The base directory of the project.
        backend_root (str): The root directory for the backend services.
        config_dir (str): The configuration directory.
        data_dir (str): The data directory.
        log_dir (str): The logs directory.
        prompts_dir (str): The directory for prompt templates.
        workflow_dir (str): The directory for workflow files.
        styles_dir (str): The directory for styles files.
        files_dir (str): The directory for project files.
        csv_dir (str): The directory for CSV data files.
        images_dir (str): The directory for images.
        ref_fullbody_dir(str): The directory for fullbody reference images.
        ref_portrait_dir(str): The directory for portrait reference images.
        approved_dir(str): The directory for approved images.
        donor_info_file (str): The filename for the donor data CSV.
        special_characteristics_weight (float): Weight for special characteristics in prompts.
        fullbody_prompt_template (str): The filename for the fullbody positive prompt template.
        portrait_prompt_template (str): The filename for the portrait positive prompt template.
        negative_prompt_template (str): The filename for the base negative prompt template.
        detailer_positive_prompt_template (str): The filename for the face detailer positive prompt template.
        detailer_negative_prompt_template (str): The filename for the face detailer negative prompt template.
        detailer_wildcard_prompt_template (str): The filename for the face detailer wildcard prompt template.
        hands_positive_prompt_template (str): The filename for the hands refiner positive prompt template.
        hands_negative_prompt_template (str): The filename for the hands refiner negative prompt template.
        log_level (str): The minimum level of messages to log (e.g., INFO, WARNING).
        log_format (str): The format for log messages.
        generation_verbose (Dict[str, Any] | bool): Verbose mode for generation.
            - bool → all or nothing.
            - dict → {'all': true} or granular control (memory|images|prompts|workflow|generation).
        save_workflow (bool): Save the current workflow in JSON format.
    """
    model_config = SettingsConfigDict(
        env_file=DOTENV_PATH,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    # --- Server Configuration ---
    fastapi_server_address: str = Field(default="127.0.0.1:8000")
    comfyui_server_address: str = Field(default="127.0.0.1:8188")

    # --- ComfyUI Container Paths ---
    comfyui_input_dir: str = Field(default="/workspace/ComfyUI_app/input")
    comfyui_reference_dir: str = Field(default="/app/reference")
    comfyui_output_dir: str = Field(default="/app/ComfyUI/output")

    # --- Images Config ---
    img_max_dimension: int = Field(default=1024)

    # --- Restart ---
    max_runs: int = Field(default=10)
    restart_timeout: int = Field(default=60)
    restart_cooldown: int = Field(default=60)

    # --- Retries ---
    max_retries: int = Field(default=1)
    retries_delay_seconds: int = Field(default=5)

    # --- Interrupt ---
    interrupt_after_seconds: int = Field(default=600)
    interrupt_wait_seconds: int = Field(default=100)

    # --- Delay ---
    delay_between_projects: int = Field(default=5)
    delay_between_cycles: int = Field(default=5)
    approved_scan_interval: int = Field(default=1)

    # --- Directory Paths ---
    base_dir: str = str(BASE_DIR)
    backend_root: str = str(BACKEND_ROOT)
    config_dir: str = str(CONFIG_DIR)
    data_dir: str = str(DATA_DIR)
    log_dir: str = str(LOG_DIR)
    prompts_dir: str = str(PROMPTS_DIR)
    workflow_dir: str = str(WORKFLOW_DIR)
    styles_dir: str = str(STYLES_DIR)
    files_dir: str = str(FILES_DIR)
    csv_dir: str = str(CSV_DIR)
    images_dir: str = str(IMAGES_DIR)
    ref_fullbody_dir: str = str(REFERECE_FB_DIR)
    ref_portrait_dir: str = str(REFERECE_PT_DIR)
    approved_dir: str = str(APPROVED_DIR)

    # --- File Paths ---
    donor_info_file: str = Field(default="donor_info.csv")

    # --- Prompt Settings ---
    special_characteristics_weight: float = Field(default=1.1)

    # --- Prompt Templates ---
    fullbody_prompt_template: str = Field(default="fullbody_positive_prompt.txt")
    portrait_prompt_template: str = Field(default="portrait_positive_prompt.txt")
    negative_prompt_template: str = Field(default="negative_prompt.txt")
    detailer_positive_prompt_template: str = Field(default="detailer_positive_prompt.txt")
    detailer_negative_prompt_template: str = Field(default="detailer_negative_prompt.txt")
    detailer_wildcard_prompt_template: str = Field(default="detailer_wildcard_prompt.txt")
    hands_positive_prompt_template: str = Field(default="hands_positive_prompt.txt")
    hands_negative_prompt_template: str = Field(default="hands_negative_prompt.txt")

    # --- Modes ---
    portrait: PortraitSettings
    fullbody: FullbodySettings

    # --- logging ---
    log_level: str = Field(default="INFO")
    log_format: str = Field(default='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    generation_verbose: Union[bool, Dict[str, Any], None] = False

    # --- Workflow ---
    save_workflow: bool = Field(default=False)

    @field_validator("generation_verbose", mode="before")
    @classmethod
    def normalize_verbose(cls, v):
        if v is True:
            return {"all": True}
        if v is False or v is None:
            return {}
        if isinstance(v, dict):
            # Si tiene "all: true", lo normalizamos también
            if v.get("all") is True:
                return {"all": True}
            return {k: bool(v) for k, v in v.items() if v is True}
        return {}
    
    def get_verbose_flag(self, section: str) -> bool:
        """
        Returns True if the given generation stage should print verbose output.

        Args:
            section: One of 'memory', 'images', 'prompts', 'workflow', 'generation'

        Returns:
            bool: True if verbose is enabled for this section (or if 'all' is active)
        """
        verbose = getattr(self, "generation_verbose", {})
        if not isinstance(verbose, dict):
            verbose = {}
        return verbose.get("all", False) or verbose.get(section, False)
    
# Global settings instance (singleton pattern)
_settings: Optional[Settings] = None

def get_settings() -> Settings:
    """
    Get application settings (singleton pattern).

    This function ensures that only one instance of the Settings class is created.
    It first attempts to load settings from a `config.yaml` file, if it exists.
    Sensitive keys are removed from the loaded dictionary before creating the Settings object.

    Raises:
        FileNotFoundError: If the 'config.yaml' file is not found.
        ValidationError: If validation of the configuration fails.

    Returns:
        Settings: The singleton instance of the application settings.
    """
    global _settings
    if _settings is None:
        config_dict = {}
        if CONFIG_PATH.exists():
            config_dict = load_yaml_file(str(CONFIG_PATH))
        else:
            raise FileNotFoundError(f"ERROR: File not found {CONFIG_PATH}")

        keys_to_remove = []
        for key in config_dict.keys():
            if key.lower() in SENSITIVE_KEYS:
                keys_to_remove.append(key)

        for key in keys_to_remove:
            del config_dict[key]
        
        try:
            portrait_data = config_dict.pop('portrait')
            fullbody_data = config_dict.pop('fullbody')

            portrait_settings = PortraitSettings(**portrait_data)
            fullbody_settings = FullbodySettings(**fullbody_data)

            _settings = Settings(
                portrait=portrait_settings,
                fullbody=fullbody_settings,
                **config_dict
            )
        except ValidationError as e:
            raise ValidationError(f"ERROR: Validation failed in configuration: {e}")

    return _settings
