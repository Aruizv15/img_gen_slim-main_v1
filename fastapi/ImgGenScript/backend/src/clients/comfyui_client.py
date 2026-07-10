import json
import logging
import websocket
from typing import Dict, List, Optional, Tuple

from backend.src.clients.base_client import BaseAPIClient


class ComfyUIClient(BaseAPIClient):
    """
    Client for interacting with the ComfyUI API.
    """

    def __init__(
        self,
        server_address: str,
        timeout: Optional[int] = 15,
        client_id: Optional[str] = None,
        logger: Optional[logging.Logger] = None
    ):
        super().__init__(
            server_address=server_address,
            timeout=timeout,
            client_id=client_id,
            logger=logger
        )

    def queue_prompt(self, prompt: Dict) -> Dict:
        payload = {"prompt": prompt, "client_id": self.client_id}
        print(f"[WORKFLOW NODES] {list(prompt.keys())}")
        output_nodes = [k for k, v in prompt.items() if v.get('class_type') in ['SaveImage', 'PreviewImage']]
        print(f"[OUTPUT NODES] {output_nodes}")
        return self.http.post("/prompt", data=payload)

    def get_images(self, ws: websocket.WebSocket, prompt: Dict) -> Dict[str, List[bytes]]:
        result = self.queue_prompt(prompt)

        if result.get("status") == "error":
            raise RuntimeError(f"Queue failed: {result['message']} | Detail: {result.get('detail', 'No detail')} | Data: {result.get('data', {})}")

        prompt_id = result["data"]["prompt_id"]
        output_images = {}
        current_node = ""

        while True:
            out = ws.recv()
            if isinstance(out, str):
                message = json.loads(out)
                if message["type"] == "executing":
                    data = message["data"]
                    if data["node"] is None and data["prompt_id"] == prompt_id:
                        break
                    else:
                        current_node = data["node"]
            else:
                if current_node not in output_images:
                    output_images[current_node] = []
                output_images[current_node].append(out[8:])

        return output_images

    def generate_images(
        self,
        workflow: Dict,
        verbose: bool = False
    ) -> List[Tuple[str, str, str]]:
        """
        Generates images and returns list of (filename, subfolder, type) tuples
        by querying the history after generation completes.
        """
        if verbose:
            print(f"[ComfyUI] Generating images with workflow nodes: {list(workflow.keys())}")

        # Queue the prompt
        result = self.queue_prompt(workflow)
        if result.get("status") == "error":
            raise RuntimeError(f"Queue failed: {result['message']} | Detail: {result.get('detail', 'No detail')} | Data: {result.get('data', {})}")

        prompt_id = result["data"]["prompt_id"]

        # Wait via WebSocket for completion
        ws, _, _ = self.open_websocket_connection()
        try:
            while True:
                out = ws.recv()
                if isinstance(out, str):
                    message = json.loads(out)
                    if message["type"] == "executing":
                        data = message["data"]
                        if data["node"] is None and data["prompt_id"] == prompt_id:
                            break
        finally:
            ws.close()

        # Get image paths from history
        history = self.get_history(prompt_id)
        image_paths = []

        if prompt_id in history:
            outputs = history[prompt_id].get("outputs", {})
            for node_id, node_output in outputs.items():
                if "images" in node_output:
                    for img in node_output["images"]:
                        image_paths.append((
                            img.get("filename", ""),
                            img.get("subfolder", ""),
                            img.get("type", "output")
                        ))

        print(f"[ComfyUI] Generated {len(image_paths)} images")
        return image_paths

    def download_images_from_paths(
        self,
        paths: List[Tuple[str, str, str]],
        verbose: bool = False
    ) -> List[Tuple[str, bytes]]:
        """
        Downloads images from ComfyUI given a list of (filename, subfolder, type) tuples.
        """
        images = []
        for filename, subfolder, folder_type in paths:
            if not filename:
                continue
            params = {"filename": filename, "subfolder": subfolder, "type": folder_type}
            result = self.http.get("/view", params=params)
            if result.get("status") == "success" and result.get("data"):
                images.append((filename, result["data"]))
                if verbose:
                    print(f"[DOWNLOAD] Downloaded: {filename}")
            else:
                if verbose:
                    print(f"[DOWNLOAD] Failed: {filename}")
        return images

    def get_history(self, prompt_id: str) -> Dict:
        result = self.http.get(f"/history/{prompt_id}")
        return result.get("data", {})

    def get_queue(self) -> Dict:
        result = self.http.get("/queue")
        return result.get("data", {})

    def interrupt(self) -> None:
        self.http.post("/interrupt")

    def free_comfyui_memory(
        self,
        unload_models: bool = True,
        free_memory: bool = True,
        verbose: bool = False
    ) -> Dict:
        payload = {"unload_models": unload_models, "free_memory": free_memory}
        if verbose:
            print(f"[ComfyUI] Freeing memory: {payload}")
        return self.http.post("/free", data=payload)

    def open_websocket_connection(self) -> Tuple[websocket.WebSocket, str, str]:
        ws = websocket.WebSocket()
        ws.connect(f"ws://{self.server_address}/ws?clientId={self.client_id}")
        return ws, self.server_address, self.client_id
