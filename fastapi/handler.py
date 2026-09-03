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
import csv
import importlib.util
import logging

nest_asyncio.apply()
import urllib.request

_h_logger = logging.getLogger(__name__)

# --- Correccion de color de ojos, aplicada justo antes de subir a B2 ---
# IMPORTANTE: el pipeline de Python (ImageGenerator.download_images/
# save_images) guarda en project_path/generation_type, una carpeta que
# esta funcion NUNCA sube -- upload_outputs_to_b2() sube directamente
# desde /workspace/ComfyUI_app/output (donde ComfyUI escribe los
# archivos nativamente via su nodo SaveImage). Por eso la correccion de
# ojos debe aplicarse ACA, sobre los archivos reales que se suben, y no
# en el pipeline paralelo de Python que nunca llega a B2.
_EYE_COLOR_MODULE_PATH = os.getenv("EYE_COLOR_CORRECTION_PATH", "/app/eye_color_correction.py")


def _load_correct_eye_color():
    try:
        if not os.path.exists(_EYE_COLOR_MODULE_PATH):
            print(f"[EYE_COLOR] No se encontro eye_color_correction.py en {_EYE_COLOR_MODULE_PATH}. Correccion desactivada.")
            return None
        spec = importlib.util.spec_from_file_location("eye_color_correction", _EYE_COLOR_MODULE_PATH)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        print(f"[EYE_COLOR] Modulo cargado correctamente desde {_EYE_COLOR_MODULE_PATH}")
        return module.correct_eye_color
    except Exception as e:
        print(f"[EYE_COLOR] Error cargando eye_color_correction.py: {e}. Correccion desactivada.")
        return None


_correct_eye_color_fn = _load_correct_eye_color()


def _get_donor_eye_color(vrepro_id):
    """
    Busca el valor de color de ojos de la donante en donor_info.csv.
    Tolerante al nombre exacto de la columna (busca cualquier header que
    contenga "eye" y "color", sin importar mayusculas) para no depender
    de adivinar el nombre exacto.
    """
    csv_path = '/workspace/ImgGenScript/files/csv/donor_info.csv'
    if not os.path.exists(csv_path):
        print(f"[EYE_COLOR] CSV no encontrado en {csv_path}")
        return None
    try:
        with open(csv_path, newline='', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f, delimiter=';')
            eye_color_col = None
            if reader.fieldnames:
                for col in reader.fieldnames:
                    if col and 'eye' in col.lower() and 'color' in col.lower():
                        eye_color_col = col
                        break
            if not eye_color_col:
                print(f"[EYE_COLOR] No se encontro columna de eye color en el CSV. Columnas disponibles: {reader.fieldnames}")
                return None
            for row in reader:
                row_id = (row.get('vreproID') or '').strip()
                if row_id == vrepro_id.strip():
                    value = row.get(eye_color_col)
                    print(f"[EYE_COLOR] Columna detectada: '{eye_color_col}' -> valor para {vrepro_id}: {value!r}")
                    return value
        print(f"[EYE_COLOR] No se encontro fila con vreproID={vrepro_id} en el CSV")
        return None
    except Exception as e:
        print(f"[EYE_COLOR] Error leyendo eye_color desde CSV: {e}")
        return None

print("=" * 60)
print("[HANDLER BUILD] v6-eye-color-en-upload-2026-09-03")
print("[HANDLER BUILD] Si NO ves '[HANDLER] Ciclo X/N generado y")
print("[HANDLER BUILD] subido a B2' entre cada ciclo mas abajo, este")
print("[HANDLER BUILD] worker esta corriendo una imagen VIEJA. Termina")
print("[HANDLER BUILD] este worker y verifica el build activo en RunPod.")
print("=" * 60)

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


try:
    _obj_info = urllib.request.urlopen(
        "http://127.0.0.1:8188/object_info/AV_ControlNetPreprocessor", timeout=10
    ).read().decode()
    print("[DEBUG PREPROCESSOR LIST] " + _obj_info)
except Exception as _e:
    print(f"[DEBUG PREPROCESSOR LIST] No se pudo obtener: {_e}")



for _node_name in ["IPAdapterFaceID", "IPAdapterAdvanced"]:
    try:
        _obj_info = urllib.request.urlopen(
            f"http://127.0.0.1:8188/object_info/{_node_name}", timeout=10
        ).read().decode()
        print(f"[DEBUG WEIGHT_TYPE LIST {_node_name}] " + _obj_info)
    except Exception as _e:
        print(f"[DEBUG WEIGHT_TYPE LIST {_node_name}] No se pudo obtener: {_e}")
# --- FIN BLOQUE TEMPORAL ---

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
            
            if filename and filename.startswith(vrepro_id):
                dl = await client.get(
                    f"{auth['downloadUrl']}/file/{bucket}/{f['fileName']}",
                    headers={"Authorization": auth["authorizationToken"]}
                )
          
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

        # Pose de referencia fija para portrait.
        # FIX: antes solo se descargaba "if not os.path.exists", asi que si una
        # descarga fallaba una vez, ningun job posterior la reintentaba y portrait
        # salia SIN pose (niebla, pelo tieso, cara descolocada). Ahora:
        #   1. Se descarga SIEMPRE, con reintentos.
        #   2. Se copia la pose a AMBAS rutas conocidas (la de ref_portrait_dir que
        #      usa processor.py para buscarla, y la comfyui_reference_dir que usa
        #      workflow_builder.py para pasarsela a ComfyUI), para que coincidan
        #      pase lo que pase. Esta era la causa raiz historica del bug de rutas.
        pose_filename = 'pose_fija_portrait.png'
        pose_dirs = [
            '/workspace/ImgGenScript/files/reference/portrait',
            os.getenv('COMFYUI_REFERENCE_DIR', '/app/reference'),
        ]
        for _d in pose_dirs:
            os.makedirs(_d, exist_ok=True)

        pose_content = None
        for intento in range(3):
            try:
                dl_pose = await client.get(
                    f"{auth['downloadUrl']}/file/{bucket}/reference/{pose_filename}",
                    headers={"Authorization": auth["authorizationToken"]}
                )
                if dl_pose.status_code == 200 and len(dl_pose.content) > 1024:
                    pose_content = dl_pose.content
                    break
                else:
                    print(f"[WARN] Pose intento {intento+1}/3: status={dl_pose.status_code}, bytes={len(dl_pose.content)}")
            except Exception as e:
                print(f"[WARN] Pose intento {intento+1}/3 excepcion: {e}")

        if pose_content is not None:
            escritas = []
            for _d in pose_dirs:
                dest = os.path.join(_d, pose_filename)
                try:
                    with open(dest, "wb") as out:
                        out.write(pose_content)
                    escritas.append(dest)
                except Exception as e:
                    print(f"[WARN] No se pudo escribir la pose en {dest}: {e}")
            print(f"[B2] Pose de referencia descargada y copiada a: {escritas}")
        else:
            # La pose es OBLIGATORIA para portrait. Si no se pudo bajar, se avisa
            # de forma RUIDOSA. El processor.py corregido hara fallar el job de
            # portrait en vez de generar una imagen sin pose en silencio.
            print(f"[ERROR] POSE FIJA NO DESCARGADA tras 3 intentos. "
                  f"Los portraits de este worker fallaran hasta que B2 responda. "
                  f"Verificar que exista reference/{pose_filename} en el bucket '{bucket}'.")

async def upload_outputs_to_b2(vrepro_id, generation_type, job_batch):
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

    # --- Correccion de color de ojos, sobre los archivos REALES que se suben ---
    if _correct_eye_color_fn is not None:
        eye_color = _get_donor_eye_color(vrepro_id)
        if eye_color:
            n_corrected = 0
            for local_path in all_files:
                try:
                    with open(local_path, 'rb') as fp:
                        original_bytes = fp.read()
                    corrected_bytes = _correct_eye_color_fn(original_bytes, eye_color)
                    if corrected_bytes is not None:
                        with open(local_path, 'wb') as fp:
                            fp.write(corrected_bytes)
                        n_corrected += 1
                except Exception as e:
                    print(f"[EYE_COLOR] Excepcion corrigiendo {local_path}: {e}")
            print(f"[EYE_COLOR] Corregidas {n_corrected}/{len(all_files)} imagenes antes de subir (color objetivo: {eye_color})")
        else:
            print(f"[EYE_COLOR] Sin color de ojos disponible para {vrepro_id} -- se sube sin corregir.")
    else:
        print("[EYE_COLOR] Modulo no disponible -- se sube sin corregir.")

    batch_ts = time.strftime('%Y%m%d-%H%M%S')

    failed_files = []
    async with httpx.AsyncClient() as client:
        for idx, local_path in enumerate(all_files):
            f = os.path.basename(local_path)
            stem, ext = os.path.splitext(f)
          
            remote_name = f"generated_images/{vrepro_id}/{generation_type}/{job_batch}/{stem}{batch_ts}-{idx:02d}{ext}"
            with open(local_path, "rb") as fp:
                content = fp.read()

            sha1 = hashlib.sha1(content).hexdigest()

          
            success = False
            for intento in range(3):
                try:
                    r = await client.get(
                        f"{auth['apiUrl']}/b2api/v2/b2_get_upload_url",
                        headers={"Authorization": auth["authorizationToken"]},
                        params={"bucketId": bucket_id}
                    )
                    upload_data = r.json()
                    resp = await client.post(
                        upload_data["uploadUrl"],
                        headers={
                            "Authorization": upload_data["authorizationToken"],
                            "X-Bz-File-Name": remote_name,
                            "Content-Type": "b2/x-auto",
                            "Content-Length": str(len(content)),
                            "X-Bz-Content-Sha1": sha1
                        },
                        content=content
                    )
                    if resp.status_code == 200:
                        print(f"[B2] Subida OK: {remote_name}")
                        success = True
                        break
                    else:
                        print(f"[B2] Intento {intento+1}/3 fallo para {f}: status={resp.status_code}, body={resp.text[:300]}")
                except Exception as e:
                    print(f"[B2] Intento {intento+1}/3 excepcion para {f}: {e}")

            if not success:
                print(f"[B2] ERROR DEFINITIVO: no se pudo subir {f} tras 3 intentos")
                failed_files.append(f)

    if failed_files:
        print(f"[B2] RESUMEN: {len(failed_files)} archivo(s) fallaron: {failed_files}")
    else:
        print(f"[B2] RESUMEN: todos los archivos ({len(all_files)}) se subieron correctamente")

def handler(job):
    sys.path.insert(0, "/workspace/ImgGenScript")
    sys.path.insert(0, "/workspace/ImgGenScript/backend")
    from backend.src.batch.orchestrator import BatchOrchestrator

    job_input = job["input"]
    vrepro_id = job_input.get("vreproID", "")
    generation_type = job_input.get("generation_type", "fullbody")
    max_cycles = job_input.get("max_cycles", 1)
 
    job_batch = job_input.get("job_batch") or time.strftime('%Y%m%d-%H%M%S')

    
    use_pose = bool(job_input.get("use_pose", False))
    use_hands_refiner = bool(job_input.get("use_hands_refiner", True))
    use_amateur_effect = bool(job_input.get("use_amateur_effect", True))

    print(f"[HANDLER] vreproID={vrepro_id}, generation_type={generation_type}, "
          f"cycles={max_cycles}, pose={use_pose}, hands={use_hands_refiner}, "
          f"amateur={use_amateur_effect}, job_batch={job_batch}")

    if not vrepro_id:
        return {"status": "error", "message": "vreproID es requerido"}

    try:
        loop = asyncio.get_event_loop()
        loop.run_until_complete(download_inputs_from_b2(vrepro_id))

        comfy_input = '/workspace/ComfyUI_app/input'
        if os.path.isdir(comfy_input):
            shutil.rmtree(comfy_input)
        os.makedirs(comfy_input, exist_ok=True)

        
        comfy_output = '/workspace/ComfyUI_app/output'
        if os.path.isdir(comfy_output):
            shutil.rmtree(comfy_output)
        os.makedirs(comfy_output, exist_ok=True)
        src = f'/workspace/ImgGenScript/files/images/{vrepro_id}'
        if os.path.isdir(src):
           
            all_files = os.listdir(src)
            if generation_type == "portrait":
                relevant_files = [f for f in all_files if "portrait" in f.lower()]
            else:
                relevant_files = [f for f in all_files if "portrait" not in f.lower()]
    
            files_to_copy = relevant_files if relevant_files else all_files
            for f in files_to_copy:
                shutil.copy2(os.path.join(src, f), os.path.join(comfy_input, f))
            print(f"[COMFYUI INPUT] Copiadas ({generation_type}): {os.listdir(comfy_input)}")

        async def main():
         
            for _ciclo in range(max_cycles):
                orchestrator = BatchOrchestrator(generation_type=generation_type)
                await orchestrator.run(
                    max_cycles=1,
                    donor_list=[vrepro_id],
                    use_pose_override=use_pose,
                    use_hands_refiner_override=use_hands_refiner,
                    use_amateur_effect_override=use_amateur_effect,
                )
               
                try:
                    _comfyui_log.flush()
                    print(f"[DEBUG COMFYUI LOG POST-CICLO] {open('/tmp/comfyui.log').read()[-4000:]}")
                except Exception as _e:
                    print(f"[DEBUG COMFYUI LOG POST-CICLO] No se pudo leer: {_e}")
                await upload_outputs_to_b2(vrepro_id, generation_type, job_batch)
      
                if os.path.isdir(comfy_output):
                    shutil.rmtree(comfy_output)
                os.makedirs(comfy_output, exist_ok=True)
                print(f"[HANDLER] Ciclo {_ciclo + 1}/{max_cycles} generado y subido a B2")

        loop.run_until_complete(main())

        return {"status": "done", "vreproID": vrepro_id}
    except Exception as e:
        import traceback
        _comfyui_log.flush()
        _fastapi_log.flush()
        print(f"[HANDLER] EXCEPCION: {e}")
        print(f"[HANDLER] TRACEBACK COMPLETO:\n{traceback.format_exc()}")
        print(f"[COMFYUI LOG FINAL]\n{open('/tmp/comfyui.log').read()[-3000:]}")
        return {"status": "error", "message": str(e)}

runpod.serverless.start({"handler": handler})
