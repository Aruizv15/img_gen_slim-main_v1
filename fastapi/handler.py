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

nest_asyncio.apply()
import urllib.request

for _d in [
    '/app/shared_data/input_images',
    '/app/shared_data/output_images',
    '/app/shared_data/reference_images',
    '/app/shared_data/temp_images',
    '/app/static',
    '/app/templates',
    '/workspace/ImgGenScript/files/reference/portrait',
    '/workspace/ImgGenScript/files/reference/fullbody',
]:
    os.makedirs(_d, exist_ok=True)

# Usar Network Volume para modelos persistentes
volume_models = '/runpod-volume/models'
comfy_models = '/workspace/ComfyUI_app/models'
os.makedirs(volume_models, exist_ok=True)
os.makedirs(f'{volume_models}/ultralytics/bbox', exist_ok=True)
os.makedirs(f'{volume_models}/ultralytics/segm', exist_ok=True)
os.makedirs(f'{volume_models}/sams', exist_ok=True)

# Forzar symlink aunque la carpeta ya exista
if os.path.isdir(comfy_models) and not os.path.islink(comfy_models):
    shutil.rmtree(comfy_models)
    os.symlink(volume_models, comfy_models)
    print(f"[MODELS] Symlink creado: {comfy_models} -> {volume_models}")
elif not os.path.exists(comfy_models):
    os.symlink(volume_models, comfy_models)
    print(f"[MODELS] Symlink creado: {comfy_models} -> {volume_models}")
else:
    print(f"[MODELS] Symlink ya existe: {comfy_models} -> {volume_models}")

# Descargar modelos solo si no existen en el volumen
flag_file = '/runpod-volume/models/.downloaded'
if not os.path.exists(flag_file):
    print("[MODELS] Descargando modelos desde HuggingFace...")
    subprocess.run(["pip", "install", "--no-cache-dir", "huggingface_hub>=0.20", "-q"], check=True)
    subprocess.run(["python", "/app/download_models.py"], check=True)
    open(flag_file, 'w').close()
    print("[MODELS] Modelos descargados correctamente")
else:
    print("[MODELS] Modelos ya en volumen, saltando...")

if not os.path.exists("/workspace/ComfyUI_app/main.py"):
    print("[ERROR] ComfyUI no encontrado")

_fastapi_log = open('/tmp/fastapi.log', 'w')
_fastapi_process = subprocess.Popen(
    ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"],
    stdout=_fastapi_log, stderr=_fastapi_log, cwd="/app"
)
print("[FASTAPI] Arrancando...")

_comfyui_log = open('/tmp/comfyui.log', 'w')
_comfyui_process = subprocess.Popen(
    ["python", "/workspace/ComfyUI_app/main.py",
     "--listen", "0.0.0.0", "--port", "8188",
     "--disable-auto-launch", "--cuda-device", "0"],
    stdout=_comfyui_log, stderr=_comfyui_log
)
print("[COMFYUI] Arrancando...")

for _i in range(30):
    if _fastapi_process.poll() is not None:
        raise RuntimeError(f"[FASTAPI] Crasheó: {open('/tmp/fastapi.log').read()[-1000:]}")
    try:
        urllib.request.urlopen("http://127.0.0.1:8000/health", timeout=2)
        print(f"[FASTAPI] Listo en {_i*2}s")
        break
    except Exception:
        time.sleep(2)
else:
    raise RuntimeError("[FASTAPI] No respondió en 60 segundos")

for _i in range(60):
    if _comfyui_process.poll() is not None:
        raise RuntimeError(f"[COMFYUI] Crasheó: {open('/tmp/comfyui.log').read()[-3000:]}")
    try:
        urllib.request.urlopen("http://127.0.0.1:8188/system_stats", timeout=2)
        print(f"[COMFYUI] Listo en {_i*5}s")
        break
    except Exception:
        time.sleep(5)
        if _i % 6 == 0:
            _comfyui_log.flush()
            print(f"[COMFYUI LOG] {open('/tmp/comfyui.log').read()[-2000:]}")
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
    async with httpx.AsyncClient() as client:
        r = await client.get(
            f"{auth['apiUrl']}/b2api/v2/b2_list_buckets",
            headers={"Authorization": auth["authorizationToken"]},
            params={"accountId": auth["accountId"], "bucketName": os.getenv('B2_BUCKET')}
        )
        buckets = r.json().get("buckets", [])
        return buckets[0]["bucketId"] if buckets else None

async def download_inputs_from_b2(vrepro_id):
    auth = await b2_authorize()
    bucket = os.getenv('B2_BUCKET')
    input_dir = f'/workspace/ImgGenScript/files/images/{vrepro_id}'
    # Limpiar la carpeta antes de descargar: si en una corrida anterior
    # (antes del filtro por donante) se guardaron ahi fotos de OTRO
    # donante, seguirian copiandose para siempre si no se borran primero.
    if os.path.isdir(input_dir):
        shutil.rmtree(input_dir)
    os.makedirs(input_dir, exist_ok=True)
    async with httpx.AsyncClient() as client:
        r = await client.get(
            f"{auth['apiUrl']}/b2api/v2/b2_list_file_names",
            headers={"Authorization": auth["authorizationToken"]},
            params={"bucketId": await get_bucket_id(auth), "prefix": "input_images/"}
        )
        for f in r.json().get("files", []):
            filename = f["fileName"].split("/")[-1]
            # Solo descargar archivos que pertenezcan a ESTE donante.
            # Sin este filtro, se descargaban las fotos de TODOS los
            # donantes que hubiera en input_images/, y luego se mezclaban
            # juntas en el mismo lote de referencia para FaceID,
            # produciendo caras que no correspondian a la persona correcta.
            if filename and filename.startswith(vrepro_id):
                dl = await client.get(
                    f"{auth['downloadUrl']}/file/{bucket}/{f['fileName']}",
                    headers={"Authorization": auth["authorizationToken"]}
                )
                # Verificar que la descarga fue exitosa y trae contenido
                # real de imagen, no un error truncado guardado como si
                # fuera la foto (causa de "image file is truncated").
                if dl.status_code != 200 or len(dl.content) < 1024:
                    print(f"[WARN] Descarga sospechosa de {filename}: status={dl.status_code}, bytes={len(dl.content)}. Se omite.")
                    continue
                with open(os.path.join(input_dir, filename), "wb") as out:
                    out.write(dl.content)
        csv_path = '/workspace/ImgGenScript/files/csv/donor_info.csv'
        os.makedirs(os.path.dirname(csv_path), exist_ok=True)
        try:
            dl = await client.get(
                f"{auth['downloadUrl']}/file/{bucket}/csv/model_data.csv",
                headers={"Authorization": auth["authorizationToken"]}
            )
            with open(csv_path, "wb") as out:
                out.write(dl.content)
        except Exception as e:
            print(f"[WARN] CSV no descargado: {e}")

async def upload_outputs_to_b2(vrepro_id):
    auth = await b2_authorize()
    bucket_id = await get_bucket_id(auth)
    output_dir = '/workspace/ComfyUI_app/output'
    all_files = []
    for root, dirs, files in os.walk(output_dir):
        for f in files:
            if f.lower().endswith(('.jpg', '.jpeg', '.png')):
                all_files.append(os.path.join(root, f))
    print(f"[B2] Archivos encontrados: {all_files}")
    if not all_files:
        print(f"[B2] No hay archivos en {output_dir}")
        return
    async with httpx.AsyncClient() as client:
        r = await client.get(
            f"{auth['apiUrl']}/b2api/v2/b2_get_upload_url",
            headers={"Authorization": auth["authorizationToken"]},
            params={"bucketId": bucket_id}
        )
        upload_data = r.json()
        for local_path in all_files:
            f = os.path.basename(local_path)
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

    print(f"[HANDLER] vreproID={vrepro_id}, generation_type={generation_type}")

    if not vrepro_id:
        return {"status": "error", "message": "vreproID es requerido"}

    try:
        loop = asyncio.get_event_loop()
        loop.run_until_complete(download_inputs_from_b2(vrepro_id))

        comfy_input = '/workspace/ComfyUI_app/input'
        if os.path.isdir(comfy_input):
            shutil.rmtree(comfy_input)
        os.makedirs(comfy_input, exist_ok=True)
        src = f'/workspace/ImgGenScript/files/images/{vrepro_id}'
        if os.path.isdir(src):
            for f in os.listdir(src):
                shutil.copy2(os.path.join(src, f), os.path.join(comfy_input, f))
            print(f"[COMFYUI INPUT] Copiadas: {os.listdir(comfy_input)}")

        async def main():
            orchestrator = BatchOrchestrator(generation_type=generation_type)
            await orchestrator.run(
                max_cycles=max_cycles,
                donor_list=[vrepro_id],
                use_pose_override=False,
                use_hands_refiner_override=False,
                use_amateur_effect_override=True,
            )

        loop.run_until_complete(main())
        loop.run_until_complete(upload_outputs_to_b2(vrepro_id))

        return {"status": "done", "vreproID": vrepro_id}
    except Exception as e:
        _comfyui_log.flush()
        _fastapi_log.flush()
        print(f"[COMFYUI LOG FINAL]\n{open('/tmp/comfyui.log').read()[-3000:]}")
        return {"status": "error", "message": str(e)}

runpod.serverless.start({"handler": handler})
