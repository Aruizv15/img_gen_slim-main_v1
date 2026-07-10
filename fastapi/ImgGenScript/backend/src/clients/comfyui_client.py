import json
import time
import logging
import websocket
from typing import Dict, List, Optional, Tuple

from backend.src.clients.base_client import BaseAPIClient


class ComfyUIClient(BaseAPIClient):

    def __init__(self, server_address, timeout=15, client_id=None, logger=None):
        super().__init__(server_address=server_address, timeout=timeout, client_id=client_id, logger=logger)

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

    def generate_images(self, workflow: Dict, verbose: bool = False) -> List[Tuple[str, str, str]]:
        if verbose:
            print(f"[ComfyUI] Generating images with workflow nodes: {list(workflow.keys())}")

        result = self.queue_prompt(workflow)
        if result.get("status") == "error":
            raise RuntimeError(f"Queue failed: {result['message']} | Detail: {result.get('detail', 'No detail')} | Data: {result.get('data', {})}")

        prompt_id = result["data"]["prompt_id"]
        print(f"[ComfyUI] Prompt ID: {prompt_id}")

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
                            print(f"[ComfyUI] Execution complete for prompt {prompt_id}")
                            break
        finally:
            ws.close()

        # Wait a moment for history to be written
        time.sleep(2)

        # Get image paths from history
        image_paths = []
        for attempt in range(5):
            history = self.get_history(prompt_id)
            print(f"[ComfyUI] History keys: {list(history.keys())}")
            if prompt_id in history:
                outputs = history[prompt_id].get("outputs", {})
                print(f"[ComfyUI] Output nodes: {list(outputs.keys())}")
                for node_id, node_output in outputs.items():
                    if "images" in node_output:
                        for img in node_output["images"]:
                            image_paths.append((
                                img.get("filename", ""),
                                img.get("subfolder", ""),
                                img.get("type", "output")
                            ))
                break
            else:
                print(f"[ComfyUI] Prompt not in history yet, waiting... (attempt {attempt+1}/5)")
                time.sleep(3)

        print(f"[ComfyUI] Generated {len(image_paths)} images: {image_paths}")
        return image_paths

    def download_images_from_paths(self, paths: List[Tuple[str, str, str]], verbose: bool = False) -> List[Tuple[str, bytes]]:
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

    def free_comfyui_memory(self, unload_models=True, free_memory=True, verbose=False) -> Dict:
        payload = {"unload_models": unload_models, "free_memory": free_memory}
        if verbose:
            print(f"[ComfyUI] Freeing memory: {payload}")
        return self.http.post("/free", data=payload)

    def open_websocket_connection(self) -> Tuple[websocket.WebSocket, str, str]:
        ws = websocket.WebSocket()
        ws.connect(f"ws://{self.server_address}/ws?clientId={self.client_id}")
        return ws, self.server_address, self.client_id
