import os
import time
import httpx
import base64
import pathlib
import docker
import uuid
import sys
import threading
import asyncio

from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from typing import List, Optional
from dotenv import load_dotenv

# ============================================================
# LOGIN — modulo separado (ver auth.py)
# ============================================================
from auth import (
    auth_router, require_login, require_login_flexible, require_admin,
    record_image_ownership, get_owned_files_for_user, get_image_owner,
    get_all_owned_files,
)


# Orchestrator solo disponible en RunPod

# Antes: un solo job global (current_job) bloqueaba correr fullbody y
# portrait al mismo tiempo. Ahora: un job independiente por generation_type,
# para poder correr ambos en paralelo.
jobs_by_type = {
    "fullbody": {"job_id": None, "status": "idle", "started_at": None, "finished_at": None, "error": None},
    "portrait": {"job_id": None, "status": "idle", "started_at": None, "finished_at": None, "error": None},
}

INPUT_IMG_DIR  = "/app/shared_data/input_images"
REF_IMG_DIR    = "/app/shared_data/reference_images"
OUTPUT_IMG_DIR = "/app/shared_data/output_images"
TEMP_IMG_DIR   = "/app/shared_data/temp_images"
CSV_DATA_PATH  = "/app/shared_data/model_data.csv"

load_dotenv()

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

async def upload_to_b2(local_path: str, b2_key: str):
    auth = await b2_authorize()
    api_url = auth["apiUrl"]
    auth_token = auth["authorizationToken"]
    bucket_id = None

    async with httpx.AsyncClient() as client:
        r = await client.get(
            f"{api_url}/b2api/v2/b2_list_buckets",
            headers={"Authorization": auth_token},
            params={"accountId": auth["accountId"], "bucketName": os.getenv('B2_BUCKET')}
        )
        buckets = r.json().get("buckets", [])
        if buckets:
            bucket_id = buckets[0]["bucketId"]

        upload_url_r = await client.get(
            f"{api_url}/b2api/v2/b2_get_upload_url",
            headers={"Authorization": auth_token},
            params={"bucketId": bucket_id}
        )
        upload_data = upload_url_r.json()

        with open(local_path, "rb") as f:
            content = f.read()

        import hashlib
        sha1 = hashlib.sha1(content).hexdigest()

        await client.post(
            upload_data["uploadUrl"],
            headers={
                "Authorization": upload_data["authorizationToken"],
                "X-Bz-File-Name": b2_key,
                "Content-Type": "b2/x-auto",
                "Content-Length": str(len(content)),
                "X-Bz-Content-Sha1": sha1
            },
            content=content
        )


async def download_generated_from_b2(vrepro_id: str) -> list:
    auth = await b2_authorize()
    api_url = auth["apiUrl"]
    auth_token = auth["authorizationToken"]
    bucket = os.getenv('B2_BUCKET')

    downloaded = []
    async with httpx.AsyncClient() as client:
        r = await client.get(
            f"{api_url}/b2api/v2/b2_list_buckets",
            headers={"Authorization": auth_token},
            params={"accountId": auth["accountId"], "bucketName": bucket}
        )
        buckets = r.json().get("buckets", [])
        if not buckets:
            print(f"[B2] Bucket no encontrado: {bucket}")
            return downloaded
        bucket_id = buckets[0]["bucketId"]

        prefix = f"generated_images/{vrepro_id}/"
        list_r = await client.get(
            f"{api_url}/b2api/v2/b2_list_file_names",
            headers={"Authorization": auth_token},
            params={"bucketId": bucket_id, "prefix": prefix}
        )
        files = list_r.json().get("files", [])
        if not files:
            print(f"[B2] No se encontraron imagenes generadas para {vrepro_id} en {prefix}")
            return downloaded

        os.makedirs(OUTPUT_IMG_DIR, exist_ok=True)
        for f in files:
            filename = f["fileName"].split("/")[-1]
            if not filename:
                continue
            dl = await client.get(
                f"{auth['downloadUrl']}/file/{bucket}/{f['fileName']}",
                headers={"Authorization": auth_token}
            )
            local_path = os.path.join(OUTPUT_IMG_DIR, filename)
            with open(local_path, "wb") as out:
                out.write(dl.content)
            downloaded.append(filename)
            print(f"[B2] Descargada a {local_path}")

    return downloaded


RESTART_TOKEN = str(os.getenv("RESTART_TOKEN"))

security = HTTPBearer()

try:
    docker_client = docker.from_env()
    DOCKER_AVAILABLE = True
except Exception as e:
    print(f"Docker socket not available: {e}")
    DOCKER_AVAILABLE = False
    docker_client = None


def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if credentials.credentials != RESTART_TOKEN:
        raise HTTPException(status_code=401, detail="Token inválido")
    return credentials.credentials


def del_all_files(path: str) -> None:
    folder = pathlib.Path(path)
    if not folder.is_dir():
        print(f"Error: '{path}' is not a valid folder.")
        return
    for item in folder.iterdir():
        if item.is_file():
            try:
                os.remove(item)
            except OSError as e:
                print(f"Error deleting file '{item}': {e}")


async def save_uploaded_images(path: str, files: List[UploadFile]) -> None:
    del_all_files(path)
    for file in files:
        try:
            file_path = os.path.join(path, file.filename)
            with open(file_path, "wb") as f:
                while contents := await file.read(1024):
                    f.write(contents)
        except Exception as e:
            print(f"Error saving file {file.filename}: {e}")
        finally:
            await file.close()


async def save_reference_image(path: str, file: UploadFile) -> str:
    os.makedirs(path, exist_ok=True)
    del_all_files(path)
    filename = file.filename
    try:
        file_path = os.path.join(path, filename)
        with open(file_path, "wb") as f:
            while contents := await file.read(1024):
                f.write(contents)
    except Exception as e:
        raise RuntimeError(f"Error saving image '{filename}': {e}")
    finally:
        await file.close()
    return filename


app = FastAPI()
# El login se registra aqui, justo despues de crear 'app'.
app.include_router(auth_router)
templates = Jinja2Templates(directory="/app/templates")

app.mount("/static", StaticFiles(directory="/app/static"), name="static")
app.mount("/images", StaticFiles(directory="/app/shared_data/output_images"), name="images")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def _check_owns_image(session: dict, vrepro_id: str, filename: str):
    """Si el usuario no es admin, bloquea el acceso solo si la imagen
    tiene un dueño registrado distinto a quien la pide. Las imagenes sin
    dueño registrado (de antes de este sistema) quedan accesibles para
    no romper el historial viejo."""
    if session.get("role") == "admin":
        return
    owner = await get_image_owner(vrepro_id, filename)
    if owner is not None and owner != session.get("u"):
        raise HTTPException(status_code=403, detail="No tienes acceso a esta imagen")


def _parse_b2_path(b2_path: str):
    """
    b2_path es todo lo que va despues de 'generated_images/'. Puede tener
    distintas profundidades segun la antigüedad de la foto:
      vreproID/filename                              (legacy, sin tipo)
      vreproID/tipo/filename                         (con tipo, sin lote)
      vreproID/tipo/lote/filename                    (formato actual)
    Devuelve (vrepro_id, filename) -- lo unico que necesita el chequeo de
    propiedad, sin importar la profundidad real de la ruta.
    """
    parts = b2_path.split("/")
    return parts[0], parts[-1]


@app.get("/view_from_b2/{b2_path:path}")
async def view_from_b2(b2_path: str, session: dict = Depends(require_login_flexible)):
    vrepro_id, filename = _parse_b2_path(b2_path)
    await _check_owns_image(session, vrepro_id, filename)
    try:
        auth = await b2_authorize()
        b2_key = f"generated_images/{b2_path}"
        async with httpx.AsyncClient() as client:
            dl = await client.get(
                f"{auth['downloadUrl']}/file/{os.getenv('B2_BUCKET')}/{b2_key}",
                headers={"Authorization": auth["authorizationToken"]}
            )
        if dl.status_code != 200:
            raise HTTPException(status_code=404, detail=f"No encontrado en B2: {b2_key}")

        from fastapi.responses import Response
        return Response(content=dl.content, media_type="image/png")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/download_from_b2/{b2_path:path}")
async def download_from_b2(b2_path: str, session: dict = Depends(require_login)):
    vrepro_id, filename = _parse_b2_path(b2_path)
    await _check_owns_image(session, vrepro_id, filename)
    try:
        auth = await b2_authorize()
        b2_key = f"generated_images/{b2_path}"
        async with httpx.AsyncClient() as client:
            dl = await client.get(
                f"{auth['downloadUrl']}/file/{os.getenv('B2_BUCKET')}/{b2_key}",
                headers={"Authorization": auth["authorizationToken"]}
            )
        if dl.status_code != 200:
            raise HTTPException(status_code=404, detail=f"No encontrado en B2: {b2_key}")

        from fastapi.responses import Response
        return Response(
            content=dl.content,
            media_type="image/png",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/", response_class=HTMLResponse)
async def read_index(request: Request):
    comfyui_port = os.getenv("COMFYUI_PORT", "8188")
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "comfyui_port": comfyui_port}
    )


@app.get("/health", status_code=status.HTTP_200_OK)
async def health_check():
    return {"status": "UP"}


@app.get("/list_images")
def list_generated_images():
    images = [
        f for f in os.listdir(OUTPUT_IMG_DIR)
        if f.lower().endswith(('.png', '.jpg', '.jpeg'))
    ]
    return {"images": images}


@app.get("/list_images_b2")
async def list_generated_images_b2(session: dict = Depends(require_login)):
    try:
        auth = await b2_authorize()
        bucket = os.getenv('B2_BUCKET')
        images = []
        async with httpx.AsyncClient() as client:
            r = await client.get(
                f"{auth['apiUrl']}/b2api/v2/b2_list_buckets",
                headers={"Authorization": auth["authorizationToken"]},
                params={"accountId": auth["accountId"], "bucketName": bucket}
            )
            buckets = r.json().get("buckets", [])
            if not buckets:
                return {"images": []}
            bucket_id = buckets[0]["bucketId"]

            start_filename = None
            while True:
                params = {"bucketId": bucket_id, "prefix": "generated_images/", "maxFileCount": 1000}
                if start_filename:
                    params["startFileName"] = start_filename
                list_r = await client.get(
                    f"{auth['apiUrl']}/b2api/v2/b2_list_file_names",
                    headers={"Authorization": auth["authorizationToken"]},
                    params=params
                )
                data = list_r.json()
                for f in data.get("files", []):
                    b2_path = f["fileName"][len("generated_images/"):]
                    parts = b2_path.split("/")
                    # Formato actual (5 partes): vreproID/tipo/lote/archivo
                    if len(parts) == 4:
                        images.append({
                            "filename": parts[3],
                            "vreproID": parts[0],
                            "generationType": parts[1],
                            "jobBatch": parts[2],
                            "b2Path": b2_path,
                        })
                    # Formato intermedio (con tipo, sin lote todavia)
                    elif len(parts) == 3:
                        images.append({
                            "filename": parts[2],
                            "vreproID": parts[0],
                            "generationType": parts[1],
                            "jobBatch": None,
                            "b2Path": b2_path,
                        })
                    # Formato viejo (legacy, sin tipo ni lote)
                    elif len(parts) == 2:
                        images.append({
                            "filename": parts[1],
                            "vreproID": parts[0],
                            "generationType": "legacy",
                            "jobBatch": None,
                            "b2Path": b2_path,
                        })
                start_filename = data.get("nextFileName")
                if not start_filename:
                    break

        # Quedarse SOLO con la corrida (lote) mas reciente por cada
        # combinacion donante+tipo. Esto es permanente y vive en el
        # servidor -- no depende de nada guardado en el navegador, asi
        # que da igual cuanto tiempo despues o desde que dispositivo se
        # consulte: siempre se ve unicamente la ultima corrida.
        # Las fotos sin lote (formato legacy/intermedio, de antes de este
        # cambio) siempre se muestran, sin competir por "mas reciente".
        latest_batch = {}
        for img in images:
            if img["jobBatch"] is None:
                continue
            key = (img["vreproID"], img["generationType"])
            if key not in latest_batch or img["jobBatch"] > latest_batch[key]:
                latest_batch[key] = img["jobBatch"]

        images = [
            img for img in images
            if img["jobBatch"] is None
            or img["jobBatch"] == latest_batch.get((img["vreproID"], img["generationType"]))
        ]

        # Los administradores ven todo. Los usuarios normales solo ven
        # las imagenes que ELLOS generaron -- las que no tienen dueño
        # registrado (de antes de este sistema) tambien se muestran,
        # para no ocultar historial viejo sin dueño conocido.
        if session.get("role") != "admin":
            username = session.get("u", "")
            owned = await get_owned_files_for_user(username)
            # Necesitamos tambien saber cuales SI tienen dueño (para
            # distinguir "sin dueño" de "de otro usuario"). Reutilizamos
            # get_image_owner por archivo seria muy lento en bucle; en
            # cambio, pedimos el set completo de propietarios registrados.
            all_owned = await get_all_owned_files()
            images = [
                img for img in images
                if (img["vreproID"], img["filename"]) in owned
                or (img["vreproID"], img["filename"]) not in all_owned
            ]

        return {"images": images}
    except Exception as e:
        return {"images": [], "error": str(e)}


async def delete_all_generated_from_b2():
    auth = await b2_authorize()
    bucket = os.getenv('B2_BUCKET')
    deleted = []
    async with httpx.AsyncClient() as client:
        r = await client.get(
            f"{auth['apiUrl']}/b2api/v2/b2_list_buckets",
            headers={"Authorization": auth["authorizationToken"]},
            params={"accountId": auth["accountId"], "bucketName": bucket}
        )
        buckets = r.json().get("buckets", [])
        if not buckets:
            return deleted
        bucket_id = buckets[0]["bucketId"]

        start_filename = None
        while True:
            params = {"bucketId": bucket_id, "prefix": "generated_images/", "maxFileCount": 1000}
            if start_filename:
                params["startFileName"] = start_filename
            list_r = await client.get(
                f"{auth['apiUrl']}/b2api/v2/b2_list_file_versions",
                headers={"Authorization": auth["authorizationToken"]},
                params=params
            )
            data = list_r.json()
            files = data.get("files", [])
            for f in files:
                await client.post(
                    f"{auth['apiUrl']}/b2api/v2/b2_delete_file_version",
                    headers={"Authorization": auth["authorizationToken"]},
                    json={"fileName": f["fileName"], "fileId": f["fileId"]}
                )
                deleted.append(f["fileName"])
            start_filename = data.get("nextFileName")
            if not start_filename:
                break
    return deleted


@app.post("/clear_images")
async def clear_images(session: dict = Depends(require_login)):
    try:
        for dir_path in [INPUT_IMG_DIR, OUTPUT_IMG_DIR, REF_IMG_DIR]:
            for file in os.listdir(dir_path):
                os.remove(os.path.join(dir_path, file))
        return {"status": "success", "message": "Copia local limpiada (Backblaze no se toco)."}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.post("/clear_images_b2_permanent")
async def clear_images_b2_permanent(_: str = Depends(require_admin)):
    try:
        deleted_b2 = await delete_all_generated_from_b2()
        return {"status": "success", "message": f"Eliminados permanentemente {len(deleted_b2)} archivo(s) de Backblaze.", "deleted": deleted_b2}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.post("/clear_output")
async def clear_output(session: dict = Depends(require_login)):
    try:
        del_all_files(OUTPUT_IMG_DIR)
        return {"status": "success", "message": "Output images cleared."}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.post("/upload_images")
async def upload_and_save_images_optional(
    images: Optional[List[UploadFile]] = File(default=[]),
    reference: Optional[UploadFile] = File(None),
    csv: Optional[UploadFile] = File(None),
    session: dict = Depends(require_login),
):
    ref_name = None
    try:
        if images:
            await save_uploaded_images(INPUT_IMG_DIR, images)
        else:
            del_all_files(INPUT_IMG_DIR)

        if reference:
            ref_name = await save_reference_image(REF_IMG_DIR, reference)
        else:
            del_all_files(REF_IMG_DIR)

        if csv:
            content = await csv.read()
            if csv.filename.endswith(('.xlsx', '.xls')):
                import pandas as pd
                import io
                df = pd.read_excel(io.BytesIO(content))
                content = df.to_csv(index=False, sep=';').encode('utf-8')
            with open(CSV_DATA_PATH, "wb") as f:
                f.write(content)
            await csv.close()

        if not images and not reference and not csv:
            return JSONResponse(
                status_code=400,
                content={"status": "error", "message": "No images, reference image, or CSV provided."}
            )

        del_all_files(TEMP_IMG_DIR)

        try:
            for f in os.listdir(INPUT_IMG_DIR):
                local = os.path.join(INPUT_IMG_DIR, f)
                await upload_to_b2(local, f"input_images/{f}")
            if csv:
                await upload_to_b2(CSV_DATA_PATH, "csv/model_data.csv")
        except Exception as e:
            print(f"[B2] Error subiendo a Backblaze: {e}")

        return {
            "status": "success",
            "message": "Upload process completed.",
            "uploaded_images_count": len(images) if images else 0,
            "reference_filename": ref_name,
            "csv_saved": csv is not None,
        }
    except Exception as e:
        print(e)
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})


@app.post("/free_vram")
async def free_memory():
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post("http://comfyui:8288/free_vram")
            if response.status_code == 200:
                return {"status": "success", "message": "VRAM freed in ComfyUI", "details": response.json()}
            return {"status": "error", "message": f"ComfyUI responded with code {response.status_code}", "response": response.text}
    except httpx.ConnectError:
        return {"status": "error", "message": "Could not connect to ComfyUI. Is port 8288 active?"}
    except httpx.TimeoutException:
        return {"status": "error", "message": "Timeout connecting to ComfyUI"}
    except Exception as e:
        return {"status": "error", "message": f"Unexpected error: {str(e)}"}


@app.get("/comfyui_status")
async def comfyui_status():
    if not DOCKER_AVAILABLE:
        return {"status": "error", "message": "Docker not available"}
    try:
        container = docker_client.containers.get("comfyui")
        attrs = container.attrs
        state = attrs['State']
        return {
            "container": "comfyui",
            "status": state['Status'],
            "started_at": state['StartedAt'],
            "pid": state['Pid'],
            "health": attrs.get('State', {}).get('Health', {}).get('Status', 'no healthcheck'),
        }
    except docker.errors.NotFound:
        return {"status": "error", "message": "Container 'comfyui' not found"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.post("/restart_comfyui")
async def restart_comfyui(token: str = Depends(verify_token)):
    if not DOCKER_AVAILABLE:
        raise HTTPException(status_code=500, detail="Docker not available in FastAPI")
    try:
        container = docker_client.containers.get("comfyui")
        if container.status != "running":
            return {"status": "warning", "message": f"ComfyUI is already {container.status}"}
        container.restart()
        time.sleep(1)
        return {"status": "success", "message": "Container 'comfyui' restarted", "timestamp": time.time()}
    except docker.errors.NotFound:
        raise HTTPException(status_code=404, detail="Container 'comfyui' not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Docker error: {str(e)}")


@app.post("/jobs")
async def start_job(
    generation_type: str = "fullbody",
    max_cycles: int = 1,
    donor_list: str = "",
    use_pose: bool = False,
    use_hands_refiner: bool = True,
    use_amateur_effect: bool = False,
    session: dict = Depends(require_login),
):
    username = session.get("u", "")
    global jobs_by_type
    if generation_type not in jobs_by_type:
        raise HTTPException(status_code=400, detail=f"generation_type invalido: {generation_type}")

    if jobs_by_type[generation_type]["status"] == "running":
        raise HTTPException(status_code=409, detail=f"Ya hay un job de {generation_type} en ejecucion.")

    job_id = str(uuid.uuid4())
    # Marca de tiempo de ESTA corrida completa (todos sus ciclos). Se usa
    # para que Backblaze agrupe todas las fotos de esta corrida juntas, y
    # para que list_images_b2 pueda quedarse SOLO con la corrida mas
    # reciente por donante+tipo -- de forma permanente, en el servidor,
    # sin depender de nada guardado en el navegador.
    job_batch = time.strftime('%Y%m%d-%H%M%S')
    donors = [d.strip() for d in donor_list.split(",") if d.strip()]

    jobs_by_type[generation_type] = {
        "job_id": job_id,
        "status": "running",
        "started_at": time.time(),
        "finished_at": None,
        "error": None,
    }

    def run():
        global jobs_by_type
        try:
            import requests as req
            runpod_api_key = os.getenv("RUNPOD_API_KEY")
            runpod_endpoint = os.getenv("RUNPOD_ENDPOINT")

            response = req.post(
                f"https://api.runpod.ai/v2/{runpod_endpoint}/run",
                headers={
                    "Authorization": f"Bearer {runpod_api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "input": {
                        "vreproID": donors[0] if donors else "",
                        "generation_type": generation_type,
                        "max_cycles": max_cycles,
                        "use_pose": use_pose,
                        "use_hands_refiner": use_hands_refiner,
                        "use_amateur_effect": use_amateur_effect,
                        "job_batch": job_batch,
                    }
                }
            )

            runpod_job = response.json()
            runpod_job_id = runpod_job.get("id")

            while True:
                status_response = req.get(
                    f"https://api.runpod.ai/v2/{runpod_endpoint}/status/{runpod_job_id}",
                    headers={"Authorization": f"Bearer {runpod_api_key}"}
                )
                status = status_response.json()

                if status.get("status") in ["COMPLETED", "FAILED"]:
                    break

                time.sleep(5)

            if status.get("status") == "COMPLETED":
                try:
                    vrepro_id = donors[0] if donors else ""
                    downloaded = asyncio.run(download_generated_from_b2(vrepro_id))
                    print(f"[JOBS] Imagenes descargadas para {vrepro_id}: {downloaded}")
                    if downloaded:
                        asyncio.run(record_image_ownership(vrepro_id, downloaded, username))
                except Exception as e:
                    print(f"[JOBS] Error descargando imagenes de B2: {e}")

            jobs_by_type[generation_type]["status"] = "done"
            jobs_by_type[generation_type]["finished_at"] = time.time()

        except Exception as e:
            jobs_by_type[generation_type]["status"] = "error"
            jobs_by_type[generation_type]["error"] = str(e)
            jobs_by_type[generation_type]["finished_at"] = time.time()

    threading.Thread(target=run, daemon=True).start()
    return {"job_id": job_id, "status": "running", "generation_type": generation_type, "message": "Batch iniciado en RunPod"}

@app.get("/jobs/current")
async def get_current_job(generation_type: Optional[str] = None, session: dict = Depends(require_login)):
    if generation_type:
        if generation_type not in jobs_by_type:
            raise HTTPException(status_code=400, detail=f"generation_type invalido: {generation_type}")
        return jobs_by_type[generation_type]

    running = [j for j in jobs_by_type.values() if j["status"] == "running"]
    if running:
        return running[0]

    finished = [j for j in jobs_by_type.values() if j["finished_at"]]
    if finished:
        return max(finished, key=lambda j: j["finished_at"])

    return jobs_by_type["fullbody"]

@app.get("/debug_b2")
async def debug_b2():
    try:
        auth = await b2_authorize()
        return {"status": "ok", "auth_response": auth}
    except Exception as e:
        return {"status": "error", "message": str(e)}
