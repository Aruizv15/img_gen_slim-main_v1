import os
import sys
import gc
import time
import runpy
import threading
import importlib
import traceback
import uvicorn
from typing import Dict, Any

from fastapi import FastAPI
from pathlib import Path

# === PATHS ===
COMFYUI_PATH = Path("/app/ComfyUI")
MAIN_PY = COMFYUI_PATH / "main.py"

HOST = os.getenv("HOST", "0.0.0.0")
COMFYUI_PORT = int(os.getenv("COMFYUI_PORT", 8188))
COMFYUI_MN_PORT = int(os.getenv("COMFYUI_MN_PORT", 8288))

if str(COMFYUI_PATH) not in sys.path:
    sys.path.insert(0, str(COMFYUI_PATH))

# === FastAPI App ===
app = FastAPI()

_node_mappings_cache: Dict[str, Any] = {}

def _get_node_class_mappings() -> Dict[str, Any]:
    """
    Dynamically imports ComfyUI's nodes.py to access NODE_CLASS_MAPPINGS.

    Caches the result to avoid repeated file loading.

    Returns:
        dict: NODE_CLASS_MAPPINGS if successful, otherwise an empty dict.
    """
    global _node_mappings_cache
    if _node_mappings_cache:
        return _node_mappings_cache

    nodes_path = os.path.join(COMFYUI_PATH, "nodes.py")
    if not os.path.exists(nodes_path):
        print(f"[ERROR] nodes.py not found: {nodes_path}")
        return {}

    try:
        print(f"[NODES] Loading {nodes_path}...")
        spec = importlib.util.spec_from_file_location("nodes", nodes_path)
        if not spec or not spec.loader:
            return {}
        mod = importlib.util.module_from_spec(spec)
        sys.modules["nodes"] = mod
        spec.loader.exec_module(mod)
        mappings = getattr(mod, "NODE_CLASS_MAPPINGS", {})
        print(f"[NODES] {len(mappings)} nodes detected")
        _node_mappings_cache = mappings
        return mappings
    except Exception as e:
        print(f"[ERROR] Failed to import nodes.py: {e}")
        print(traceback.format_exc())
        return {}
    
@app.get("/health")
def health() -> Dict[str, Any]:
    """
    Health check endpoint that reports server status and loaded node count.

    Triggers dynamic import of nodes.py if not already cached.

    Returns:
        dict: Server status, node count, and current time.
    """
    return {
        "status": "alive",
        "nodes": len(_get_node_class_mappings()),
        "time": time.strftime("%H:%M:%S")
    }

@app.get("/stats")
def stats() -> Dict[str, Any]:
    """
    Comprehensive server statistics.

    Combines health, VRAM usage, and timestamp.

    Returns:
        dict: All-in-one status report.
    """
    vram = vram_status()
    return {
        "server": "alive",
        "nodes": len(_get_node_class_mappings()),
        "vram": vram if isinstance(vram, dict) and vram.get("cuda") != False else {"cuda": False},
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    }

@app.get("/vram")
def vram_status() -> Dict[str, Any]:
    """
    Returns current CUDA memory usage statistics.

    Reports allocated, reserved, and total GPU memory in GB, plus GPU name.

    Returns:
        dict: Memory stats if CUDA is available, otherwise CUDA status.
    """
    try:
        import torch
        if not torch.cuda.is_available():
            return {"cuda": False, "message": "CUDA not available"}

        props = torch.cuda.get_device_properties(0)
        return {
            "allocated_gb": round(torch.cuda.memory_allocated() / (1024**3), 2),
            "reserved_gb": round(torch.cuda.memory_reserved() / (1024**3), 2),
            "total_gb": round(props.total_memory / (1024**3), 2),
            "gpu_name": props.name
        }
    except Exception as e:
        return {"error": str(e)}
    
@app.post("/reload-nodes")
def reload_nodes() -> Dict[str, Any]:
    """
    Forces reload of nodes.py (useful after installing new custom nodes).

    Clears cache and re-imports the module.

    Returns:
        dict: Reload status and new node count.
    """
    global _node_mappings_cache
    _node_mappings_cache = {}
    nodes = len(_get_node_class_mappings())
    return {"status": "reloaded", "nodes": nodes}

@app.post("/free_vram")
def free_vram():
    """
    Frees all loaded models and VRAM using ComfyUI's internal model management.

    Uses comfy.model_management to unload models and clear CUDA cache.
    Measures VRAM before and after cleanup.

    Returns:
        dict: Status, number of unloaded models, and VRAM freed/remaining in GB.
    """
    try:
        import torch
        import comfy.model_management as mm

        unloaded = mm.unload_all_models()
        mm.soft_empty_cache()

        before = 0.0
        after = 0.0

        if torch.cuda.is_available():
            before = torch.cuda.memory_allocated() / (1024**3)
            torch.cuda.empty_cache()
            torch.cuda.ipc_collect()
            after = torch.cuda.memory_allocated() / (1024**3)

        freed = before - after

        gc.collect()

        print(f"[VRAM] Freed {unloaded} models, {freed:.2f} GB VRAM")
        return {
            "status": "success",
            "unloaded_models": unloaded or 0,
            "vram_freed_gb": round(freed, 2),
            "vram_current_gb": round(after, 2)
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

# === API Thread ===
def run_api():
    print(f"[API] Starting on http://{HOST}:{COMFYUI_MN_PORT}")
    uvicorn.run(app, host=HOST, port=COMFYUI_MN_PORT, log_level="warning")

# === Run ComfyUI ===
def run_comfyui():
    print(f"[COMFYUI] Running {MAIN_PY} as __main__...")
    args_list = [
        "--listen", HOST,
        "--port", str(COMFYUI_PORT),
        "--front-end-version", "latest",
        "--lowvram",
        "--cache-none",
        "--force-fp16",
        "--dont-upcast-attention",
        "--disable-smart-memory",
        "--disable-xformers",
        "--preview-method", "latent2rgb",
    ]
    sys.argv = [str(MAIN_PY)] + [str(arg) for arg in args_list]
    runpy.run_path(str(MAIN_PY), run_name="__main__")
# === Main ===
if __name__ == "__main__":
    api_thread = threading.Thread(target=run_api, daemon=True)
    api_thread.start()
    
    time.sleep(1)
    
    try:
        run_comfyui()
    except KeyboardInterrupt:
        print("\n[LAUNCHER] Stop requested.")
    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()