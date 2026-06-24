from backend.src.clients.fastapi_client import FastAPIClient
from backend.src.clients.comfyui_client import ComfyUIClient

class MemoryManager:
    """
    Manages GPU memory (VRAM) by coordinating cleanup across multiple clients.

    This class provides a unified interface to trigger memory-freeing operations
    on the ComfyUI instance. It uses a two-pronged approach:
    1.  It calls a dedicated endpoint on the `FastAPIClient`, which may have
        its own logic for memory management (e.g., in a containerized environment).
    2.  It directly calls the ComfyUI server's `/free` endpoint via the
        `ComfyUIClient` to unload models and release cached memory.

    This ensures that memory is freed as effectively as possible before and after
    a generation task.
    """

    def __init__(self, comfy_client: ComfyUIClient, fastapi_client: FastAPIClient):
        """
        Initializes the MemoryManager.

        Args:
            comfy_client (ComfyUIClient): An instance of ComfyUIClient.
            fastapi_client (FastAPIClient): An instance of FastAPIClient.
        """
        self.comfy = comfy_client
        self.fastapi = fastapi_client

    def free_all(self, unload_models: bool = True, verbose: bool = False) -> None:
        """
        Frees VRAM on both the FastAPI backend and directly on ComfyUI.

        Args:
            unload_models (bool, optional): If True, instructs the ComfyUI server to unload models from VRAM.
            verbose (bool, optional): If True, prints status messages.
        """
        self.fastapi.free_vram(verbose=verbose)
        self.comfy.free_comfyui_memory(unload_models=unload_models, free_memory=True, verbose=verbose)
