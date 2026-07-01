import os
import sys
import time
import shutil
import subprocess
import httpx

# ── Variables de entorno ──────────────────────────────────────────────────────
COMFYUI_URL   = os.getenv("COMFYUI_URL", "http://127.0.0.1:8188")
COMFYUI_INPUT = os.getenv("COMFYUI_INPUT_DIR", "/workspace/ComfyUI_app/input")
B2_KEY_ID     = os.getenv("B2_KEY_ID")
B2_APP_KEY    = os.getenv("B2_APP_KEY")
B2_BUCKET     = os.getenv("B2_BUCKET", "batchapp-storage")
B2_ENDPOINT   = os.getenv("B2_ENDPOINT", "https://s3.us-east-005.backblazeb2.com")

IMGGEN_PATH   = "/workspace/ImgGenScript"
SHARED_INPUT  = "/app/shared_data/input_images"
SHARED_OUTPUT = "/app/shared_data/output_images"
SHARED_CSV    = "/app/shared_data/csv"

sys.path.insert(0, IMGGEN_PATH)

# ── Backblaze B2 ──────────────────────────────────────────────────────────────
def b2_authorize():
    import base64
    creds = base64.b64encode(f"{B2_KEY_ID}:{B2_APP_KEY}".encode()).decode()
    r = httpx.get(
        "https://api.backblazeb2.com/b2api/v2/b2_authorize_account",
        headers={"Authorization": f"Basic {creds}"},
        timeout=30,
    )
    r.raise_for_status()
    d = r.json()
    return d["authorizationToken"], d["apiUrl"], d["downloadUrl"]

def _get_bucket_id(auth_token, api_url):
    r = httpx.post(
        f"{api_url}/b2api/v2/b2_list_buckets",
        headers={"Authorization": auth_token},
        json={"accountId": B2_KEY_ID[:12]},
        timeout=30,
    )
    r.raise_for_status()
    for b in r.json()["buckets"]:
        if b["bucketName"] == B2_BUCKET:
            return b["bucketId"]
    raise RuntimeError(f"Bucket {B2_BUCKET} no encontrado")

def b2_list_files(auth_token, api_url, prefix):
    r = httpx.post(
        f"{api_url}/b2api/v2/b2_list_file_names",
        headers={"Authorization": auth_token},
        json={"bucketId": _get_bucket_id(auth_token, api_url), "prefix": prefix, "maxFileCount": 1000},
        timeout=30,
    )
    r.raise_for_status()
    return [f["fileName"] for f in r.json()["files"]]

def b2_download_file(auth_token, download_url, file_name, local_path):
    os.makedirs(os.path.dirname(local_path), exist_ok=True)
    r = httpx.get(
        f"{download_url}/file/{B2_BUCKET}/{file_name}",
        headers={"Authorization": auth_token},
        timeout=120,
    )
    r.raise_for_status()
    with open(local_path, "wb") as f:
        f.write(r.content)
    print(f"[B2] Descargado: {file_name}", flush=True)

def b2_upload_file(auth_token, api_url, local_path, b2_key):
    r = httpx.post(
        f"{api_url}/b2api/v2/b2_get_upload_url",
        headers={"Authorization": auth_token},
        json={"bucketId": _get_bucket_id(auth_token, api_url)},
        timeout=30,
    )
    r.raise_for_status()
    upload_data = r.json()
    with open(local_path, "rb") as f:
        content = f.read()
    import hashlib
    sha1 = hashlib.sha1(content).hexdigest()
    r = httpx.post(
        upload_data["uploadUrl"],
        headers={
            "Authorization": upload_data["authorizationToken"],
            "X-Bz-File-Name": b2_key,
            "Content-Type": "b2/x-auto",
            "X-Bz-Content-Sha1": sha1,
        },
        content=content,
        timeout=300,
    )
    r.raise_for_status()
    print(f"[B2] Subido: {b2_key}", flush=True)

# ── ComfyUI ───────────────────────────────────────────────────────────────────
_comfyui_process = None

def start_comfyui():
    global _comfyui_process
    print("[COMFYUI] Arrancando...", flush=True)
    log = open("/tmp/comfyui.log", "w")
    _comfyui_process = subprocess.Popen(
        [
            "python", "/workspace/ComfyUI_app/main.py",
            "--listen", "0.0.0.0",
            "--port", "8188",
            "--disable-auto-launch",
            "--cuda-device", "0",
        ],
        stdout=log,
        stderr=log,
    )

def wait_for_comfyui(timeout=300):
    start = time.time()
    while time.time() - start < timeout:
        try:
            r = httpx.get(f"{COMFYUI_URL}/system_stats", timeout=5)
            if r.status_code == 200:
                print("[COMFYUI] Listo", flush=True)
                return
        except Exception:
            pass
        time.sleep(3)
    log = open("/tmp/comfyui.log").read()[-2000:]
    raise RuntimeError(f"[COMFYUI] No respondió en {timeout}s:\n{log}")

# ── Preparar archivos ─────────────────────────────────────────────────────────
def prepare_input_files(vrepro_id, auth_token, api_url, download_url):
    """
    Descarga fotos de B2 y las copia al directorio de input de ComfyUI.
    FIX CLAVE: ComfyUI lee desde COMFYUI_INPUT/{vrepro_id}/
    El settings.py tenía comfyui_input_dir=/app/input que estaba vacío.
    """
    local_input = os.path.join(SHARED_INPUT, vrepro_id)
    os.makedirs(local_input, exist_ok=True)

    # Descargar fotos desde B2
    files = b2_list_files(auth_token, api_url, f"input_images/{vrepro_id}/")
    for b2_key in files:
        filename = os.path.basename(b2_key)
        b2_download_file(auth_token, download_url, b2_key, os.path.join(local_input, filename))

    # Copiar al input de ComfyUI (aquí es donde el Orchestrator las busca)
    comfyui_dir = os.path.join(COMFYUI_INPUT, vrepro_id)
    if os.path.exists(comfyui_dir):
        shutil.rmtree(comfyui_dir)
    shutil.copytree(local_input, comfyui_dir)
    print(f"[INPUT] Fotos en ComfyUI: {comfyui_dir}", flush=True)

    return comfyui_dir

def prepare_csv(auth_token, download_url):
    os.makedirs(SHARED_CSV, exist_ok=True)
    try:
        b2_download_file(auth_token, download_url, "csv/model_data.csv",
                         os.path.join(SHARED_CSV, "model_data.csv"))
    except Exception as e:
        print(f"[B2] CSV no disponible: {e}", flush=True)

def collect_outputs(vrepro_id):
    output_dir = os.path.join(SHARED_OUTPUT, vrepro_id)
    os.makedirs(output_dir, exist_ok=True)
    comfyui_output = "/workspace/ComfyUI_app/output"
    images = []
    if os.path.exists(comfyui_output):
        for f in os.listdir(comfyui_output):
            if f.lower().endswith((".png", ".jpg", ".jpeg")):
                src = os.path.join(comfyui_output, f)
                dst = os.path.join(output_dir, f)
                shutil.copy2(src, dst)
                images.append(dst)
    return images

def upload_outputs(images, vrepro_id, auth_token, api_url):
    uploaded = []
    for local_path in images:
        b2_key = f"output_images/{vrepro_id}/{os.path.basename(local_path)}"
        b2_upload_file(auth_token, api_url, local_path, b2_key)
        uploaded.append(b2_key)
    return uploaded

# ── Orchestrator ──────────────────────────────────────────────────────────────
def run_orchestrator(vrepro_id, generation_type):
    # Apuntar el Orchestrator al directorio correcto de ComfyUI
    os.environ["COMFYUI_SERVER_ADDRESS"] = "127.0.0.1:8188"
    os.environ["FASTAPI_SERVER_ADDRESS"] = "127.0.0.1:8000"
    os.environ["COMFYUI_INPUT_DIR"] = COMFYUI_INPUT

    from backend.src.batch.orchestrator import run_batch
    print(f"[ORCHESTRATOR] {vrepro_id} tipo={generation_type}", flush=True)
    run_batch(
        generation_type=generation_type,
        max_cycles=1,
        donor_list=[vrepro_id],
    )
    print(f"[ORCHESTRATOR] Completado {vrepro_id}", flush=True)

# ── Handler RunPod ────────────────────────────────────────────────────────────
def handler(job):
    job_input       = job.get("input", {})
    vrepro_id       = job_input.get("vrepro_id")
    generation_type = job_input.get("generation_type", "fullbody")

    if not vrepro_id:
        return {"error": "Falta vrepro_id en el input"}

    print(f"[JOB] vrepro_id={vrepro_id} tipo={generation_type}", flush=True)

    # 1. Autorizar B2
    auth_token, api_url, download_url = b2_authorize()

    # 2. Arrancar ComfyUI
    start_comfyui()
    wait_for_comfyui()

    # 3. Preparar archivos (FIX)
    prepare_input_files(vrepro_id, auth_token, api_url, download_url)
    prepare_csv(auth_token, download_url)

    # 4. Ejecutar Orchestrator
    run_orchestrator(vrepro_id, generation_type)

    # 5. Recoger outputs
    images = collect_outputs(vrepro_id)
    print(f"[OUTPUT] {len(images)} imágenes", flush=True)

    if not images:
        return {"error": "No se generaron imágenes", "vrepro_id": vrepro_id}

    # 6. Subir a B2
    uploaded = upload_outputs(images, vrepro_id, auth_token, api_url)

    return {
        "status": "ok",
        "vrepro_id": vrepro_id,
        "images_generated": len(images),
        "output_keys": uploaded,
    }

import runpod
runpod.serverless.start({"handler": handler})
