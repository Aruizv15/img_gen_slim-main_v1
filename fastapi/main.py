import os
import time
import httpx
import base64
import pathlib
import docker
import uuid
import sys
import threading

from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from typing import List, Optional
from dotenv import load_dotenv


# Orchestrator solo disponible en RunPod

current_job = {
    "job_id": None,
    "status": "idle",
    "started_at": None,
    "finished_at": None,
    "error": None
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


@app.post("/clear_images")
async def clear_images():
    try:
        for dir_path in [INPUT_IMG_DIR, OUTPUT_IMG_DIR, REF_IMG_DIR]:
            for file in os.listdir(dir_path):
                os.remove(os.path.join(dir_path, file))
        return {"status": "success", "message": "All images cleared."}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.post("/clear_output")
async def clear_output():
    """Clears only the output_images directory (used between sequential model runs)."""
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
):
    """
    Accepts model input images, an optional pose reference image, and/or a CSV file
    with model characteristics (vreproID, age, skinTone, etc.).
    The CSV is saved to shared_data so the orchestrator can read it.
    """
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
                import openpyxl
                import io
                import csv as csv_module
                wb = openpyxl.load_workbook(io.BytesIO(content))
                ws = wb.active
                csv_buffer = io.StringIO()
                writer = csv_module.writer(csv_buffer)
                for row in ws.iter_rows(values_only=True):
                    writer.writerow(row)
                content = csv_buffer.getvalue().encode('utf-8')
            with open(CSV_DATA_PATH, "wb") as f:
                f.write(content)
            await csv.close()

        if not images and not reference and not csv:
            return JSONResponse(
                status_code=400,
                content={"status": "error", "message": "No images, reference image, or CSV provided."}
            )

        del_all_files(TEMP_IMG_DIR)

        # Subir a Backblaze
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
):
    global current_job
    if current_job["status"] == "running":
        raise HTTPException(status_code=409, detail="Ya hay un job en ejecución.")

    job_id = str(uuid.uuid4())
    donors = [d.strip() for d in donor_list.split(",") if d.strip()]
    
    current_job = {
        "job_id": job_id,
        "status": "running",
        "started_at": time.time(),
        "finished_at": None,
        "error": None,
    }

    def run():
        global current_job
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
                    }
                }
            )
            
            runpod_job = response.json()
            runpod_job_id = runpod_job.get("id")
            
            # Espera el resultado
            while True:
                status_response = req.get(
                    f"https://api.runpod.ai/v2/{runpod_endpoint}/status/{runpod_job_id}",
                    headers={"Authorization": f"Bearer {runpod_api_key}"}
                )
                status = status_response.json()
                
                if status.get("status") in ["COMPLETED", "FAILED"]:
                    break
                    
                time.sleep(5)
            
            current_job["status"] = "done"
            current_job["finished_at"] = time.time()
            
        except Exception as e:
            current_job["status"] = "error"
            current_job["error"] = str(e)
            current_job["finished_at"] = time.time()

    threading.Thread(target=run, daemon=True).start()
    return {"job_id": job_id, "status": "running", "message": "Batch iniciado en RunPod"}

@app.get("/jobs/current")
async def get_current_job():
    return current_job

@app.get("/debug_b2")
async def debug_b2():
    try:
        auth = await b2_authorize()
        return {"status": "ok", "auth_response": auth}
    except Exception as e:
        return {"status": "error", "message": str(e)}