import subprocess
subprocess.run(["pip", "install", "torchsde", "-q"], check=True)

import runpod
import os
import sys
import asyncio
import hashlib
import base64
import httpx
import nest_asyncio
import subprocess
import time
import shutil
import json

nest_asyncio.apply()

import urllib.request

# Crear directorios requeridos por FastAPI
for _d in [
    '/app/shared_data/input_images',
    '/app/shared_data/output_images',
    '/app/shared_data/reference_images',
    '/app/shared_data/temp_images',
    '/app/static',
    '/app/templates',
]:
    os.makedirs(_d, exist_ok=True)

# Verificar ComfyUI
if not os.path.exists("/workspace/ComfyUI_app/main.py"):
    print("[ERROR] ComfyUI no encontrado en /workspace/ComfyUI_app/main.py")
    for root, dirs, _ in os.walk("/workspace", topdown=True):
        dirs[:] = [d for d in dirs if d not in ['__pycache__']]
        if root.replace("/workspace", "").count(os.sep) < 3:
            print(f"[DIR] {root}")
        break

# Arrancar FastAPI y ComfyUI en paralelo
_fastapi_log = open('/tmp/fastapi.log', 'w')
_fastapi_process = subprocess.Popen(
    ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"],
    stdout=_fastapi_log,
    stderr=_fastapi_log,
    cwd="/app"
)
print("[FASTAPI] Arrancando...")

_comfyui_log = open('/tmp/comfyui.log', 'w')
_comfyui_process = subprocess.Popen(
    [
        "python", "/workspace/ComfyUI_app/main.py",
        "--listen", "0.0.0.0",
        "--port", "8188",
        "--disable-auto-launch",
        "--cuda-device", "0",
    ],
    stdout=_comfyui_log,
    stderr=_comfyui_log
)
print("[COMFYUI] Arrancando...")

# Esperar FastAPI (máx 60s)
for _i in range(30):
    if _fastapi_process.poll() is not None:
        _fastapi_log.flush()
        raise RuntimeError(f"[FASTAPI] Crasheó: {open('/tmp/fastapi.log').read()[-1000:]}")
    try:
        urllib.request.urlopen("http://127.0.0.1:8000/health", timeout=2)
        print(f"[FASTAPI] Listo en {_i*2}s")
        break
    except Exception:
        time.sleep(2)
        if _i % 5 == 0:
            _fastapi_log.flush()
            print(f"[FASTAPI LOG] {open('/tmp/fastapi.log').read()[-300:]}")
else:
    raise RuntimeError("[FASTAPI] No respondió en 60 segundos")

# Esperar ComfyUI (máx 5 min)
for _i in range(60):
    if _comfyui_process.poll() is not None:
        _comfyui_log.flush()
        raise RuntimeError(f"[COMFYUI] Crasheó: {open('/tmp/comfyui.log').read()[-1000:]}")
    try:
        urllib.request.urlopen("http://127.0.0.1:8188/system_stats", timeout=2)
        print(f"[COMFYUI] Listo en {_i*5}s")
        # Verificar nodos disponibles en ComfyUI
        resp = urllib.request.urlopen("http://127.0.0.1:8188/object_info", timeout=10)
        nodes = json.loads(resp.read())
        custom_nodes = [k for k in nodes.keys() if any(x in k for x in ['easy', 'Inspire', 'AV_', 'IPAdapter', 'FaceDetailer', 'Ultralytic', 'DWPre', 'MeshGraph', 'LoadImagesFromDir'])]
        print(f"[NODES CHECK] {custom_nodes}")
        break
    except Exception:
        time.sleep(5)
        if _i % 6 == 0:
            _comfyui_log.flush()
            print(f"[COMFYUI LOG] {open('/tmp/comfyui.log').read()[-500:]}")
else:
    raise RuntimeError("[COMFYUI] No respondió en 5 minutos")

async def b2_authorize():
    key_id = os.getenv('B2_KEY_ID')
    app_key = os.getenv('B2_APP_KEY')
    credentials = base64.b64encode(f"{key_id}:{app_key}".encode()).decode()
    async with httpx.AsyncClient() as client:
        r = await client.get(
            "https://api.backblazeb2.com/b2api/v2/b2_authorize_account",
            headers={"Authorization": f"Basic {credentials}"}
        )
        return r.json()

async def get_bucket_id(auth):
    api_url = auth["apiUrl"]
    auth_token = auth["authorizationToken"]
    async with httpx.AsyncClient() as client:
        r = await client.get(
            f"{api_url}/b2api/v2/b2_list_buckets",
            headers={"Authorization": auth_token},
            params={"accountId": auth["accountId"], "bucketName": os.getenv('B2_BUCKET')}
        )
        buckets = r.json().get("buckets", [])
        return buckets[0]["bucketId"] if buckets else None

async def download_inputs_from_b2(vrepro_id):
    auth = await b2_authorize()
    api_url = auth["apiUrl"]
    auth_token = auth["authorizationToken"]
    download_url = auth["downloadUrl"]
    bucket = os.getenv('B2_BUCKET')

    input_dir = f'/workspace/ImgGenScript/files/images/{vrepro_id}'
    os.makedirs(input_dir, exist_ok=True)

    async with httpx.AsyncClient() as client:
        r = await client.get(
            f"{api_url}/b2api/v2/b2_list_file_names",
            headers={"Authorization": auth_token},
            params={"bucketId": await get_bucket_id(auth), "prefix": "input_images/"}
        )
        files = r.json().get("files", [])
        for f in files:
            filename = f["fileName"].split("/")[-1]
            if filename:
                dl = await client.get(
                    f"{download_url}/file/{bucket}/{f['fileName']}",
                    headers={"Authorization": auth_token}
                )
                with open(os.path.join(input_dir, filename), "wb") as out:
                    out.write(dl.content)

        csv_path = '/workspace/ImgGenScript/files/csv/donor_info.csv'
        os.makedirs(os.path.dirname(csv_path), exist_ok=True)
        try:
            dl = await client.get(
                f"{download_url}/file/{bucket}/csv/model_data.csv",
                headers={"Authorization": auth_token}
            )
            with open(csv_path, "wb") as out:
                out.write(dl.content)
        except Exception as e:
            print(f"[WARN] CSV no descargado: {e}")

async def upload_outputs_to_b2(vrepro_id):
    auth = await b2_authorize()
    api_url = auth["apiUrl"]
    auth_token = auth["authorizationToken"]
    bucket_id = await get_bucket_id(auth)
    output_dir = '/workspace/ComfyUI_app/output'

    if not os.path.isdir(output_dir):
        return

    async with httpx.AsyncClient() as client:
        r = await client.get(
            f"{api_url}/b2api/v2/b2_get_upload_url",
            headers={"Authorization": auth_token},
            params={"bucketId": bucket_id}
        )
        upload_data = r.json()

        for f in os.listdir(output_dir):
            if f.lower().endswith(('.jpg', '.jpeg', '.png')):
                local_path = os.path.join(output_dir, f)
                with open(local_path, "rb") as fp:
                    content = fp.read()
                sha1 = hashlib.sha1(content).hexdigest()
                await client.post(
                    upload_data["uploadUrl"],
                    headers={
                        "Authorization": upload_data["authorizationToken"],
                        "X-Bz-File-Name": f"generated_images/{vrepro_id}/{f}",
                        "Content-Type": "b2/x-auto",
                        "Content-Length": str(len(content)),
                        "X-Bz-Content-Sha1": sha1
                    },
                    content=content
                )
                print(f"[B2] Subida: generated_images/{vrepro_id}/{f}")

def handler(job):
    sys.path.insert(0, "/workspace/ImgGenScript")
    sys.path.insert(0, "/workspace/ImgGenScript/backend")

    from backend.src.batch.orchestrator import BatchOrchestrator

    job_input = job["input"]
    vrepro_id = job_input.get("vreproID", "")
    generation_type = job_input.get("generation_type", "fullbody")
    max_cycles = job_input.get("max_cycles", 1)

    print(f"[HANDLER] vreproID={vrepro_id}, generation_type={generation_type}, max_cycles={max_cycles}")

    if not vrepro_id:
        return {"status": "error", "message": "vreproID es requerido"}

    try:
        loop = asyncio.get_event_loop()

        print(f"[B2] Descargando inputs para {vrepro_id}")
        loop.run_until_complete(download_inputs_from_b2(vrepro_id))

        # Copiar imágenes a la carpeta de input de ComfyUI
        comfy_input = '/workspace/ComfyUI_app/input'
        os.makedirs(comfy_input, exist_ok=True)
        src = f'/workspace/ImgGenScript/files/images/{vrepro_id}'
        if os.path.isdir(src):
            for f in os.listdir(src):
                shutil.copy2(os.path.join(src, f), os.path.join(comfy_input, f))
            print(f"[COMFYUI INPUT] Copiadas imágenes: {os.listdir(comfy_input)}")

        async def main():
            orchestrator = BatchOrchestrator(generation_type=generation_type)
            await orchestrator.run(
                max_cycles=max_cycles,
                donor_list=[vrepro_id],
                use_pose_override=False,
                use_hands_refiner_override=True,
                use_amateur_effect_override=False,
            )

        loop.run_until_complete(main())

        print(f"[B2] Subiendo outputs de {vrepro_id}")
        loop.run_until_complete(upload_outputs_to_b2(vrepro_id))

        return {"status": "done", "vreproID": vrepro_id}
    except Exception as e:
        _comfyui_log.flush()
        _fastapi_log.flush()
        print(f"[COMFYUI LOG FINAL]\n{open('/tmp/comfyui.log').read()[-2000:]}")
        print(f"[FASTAPI LOG FINAL]\n{open('/tmp/fastapi.log').read()[-500:]}")
        return {"status": "error", "message": str(e)}

runpod.serverless.start({"handler": handler})
