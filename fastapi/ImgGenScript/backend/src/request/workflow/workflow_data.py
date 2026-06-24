from dataclasses import dataclass
from abc import ABC

@dataclass
class WorkflowData(ABC):
    """
    An abstract base class for ComfyUI workflow configuration data.

    This class defines the minimum set of common parameters required for any
    ComfyUI workflow execution within this application. Subclasses should
    extend this to include specific parameters for their respective workflows.

    Args:
        workflow_path (str): The file path to the workflow's JSON definition.
        checkpoint (str): The name of the checkpoint model to use (.safetensors).
        batch_size (int): The number of images to generate in a single batch.
        ref_directory (str): The path to the directory containing the donor's reference images.
        positive_prompt_template (str): The string content of the positive prompt template.
        negative_prompt_template (str): The string content of the negative prompt template.
    """
    workflow_path: str
    checkpoint: str
    batch_size: int
    ref_directory: str
    positive_prompt_template: str
    negative_prompt_template: str