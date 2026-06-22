# Image Generator (Dockerized Backend)

**Dockerized ComfyUI + FastAPI backend** for generating realistic model photos from reference images using AI.

Designed as an **internal service** to be consumed by external applications via API.

---

## Table of Contents

- [Architecture](#architecture)
- [Requirements](#requirements)
- [Environment Setup (Windows / Linux)](#environment-setup-windows--linux)
- [Common Setup Steps](#common-setup-steps)
- [Quick Start](#quick-start)
- [Initial Configuration](#initial-configuration)
- [FastAPI Endpoints](#fastapi-endpoints)
- [ComfyUI API Endpoints](#comfyui-api-endpoints)
- [Using ComfyUI (Optional)](#using-comfyui-optional)
- [Docker Commands Cheat Sheet](#docker-commands-cheat-sheet)
- [Resource Management](#resource-management)
- [License](#license)

---

## Architecture

```
[External App]
     │
     ├── GET  /health         → Health check
     ├── GET  /list_images    → Lists generated images
     ├── GET  /comfyui_status → Gets ComfyUI container status
     ├── POST /upload_images  → Saves to shared_data/input_images + reference_images
     ├── POST /clear_images   → Deletes all images
     ├── POST /free_vram      → Frees VRAM on ComfyUI
     ├── POST /restart_comfyui→ Restarts the ComfyUI container (requires token)
     ├── POST /prompt         → Sends generation request (workflow JSON) to ComfyUI API
     ├── POST /interrupt      → Interrupts current generation on ComfyUI API
     ├───────────────────────────────┐
[FastAPI] ↔ (shared volumes) ↔ [ComfyUI]
           
```

- **FastAPI**: Lightweight API (port `8000`) for image upload/clear.
- **ComfyUI**: Generation engine (port `8188`) with GPU acceleration.
- **Communication**: Exclusively via **shared volumes** (`shared_data/`).
- **No functional frontend**: `index.html` is a simple landing page with links to the API documentation and the ComfyUI interface.

---

### Directory Structure
```
. 
├── .env
├── check_resources.sh
├── docker-compose.yml 
├── README.md 
├── comfyui/
│ ├── Dockerfile
│ ├── requirements.txt
│ ├── launcher/
│ │   └── comfyui_launcher.py
│ └── volumes/
│   ├── custom_nodes/
│   ├── models/
│   │ ├── checkpoints/ 
│   │ ├── clip_vision/ 
│   │ ├── controlnet/
│   │ ├── insightface/
│   │ ├── ipadapter/ 
│   │ ├── loras/ 
│   │ ├── onnx/ 
│   │ ├── ultralytics/ 
│   │ └── vae/
│   └── scripts/
├── fastapi/
│ ├── Dockerfile
│ ├── requirements.txt
│ ├── main.py
│ ├── static/
│ │ ├── assets/
│ │ ├── css/
│ │ └── js/
│ └── templates/
│   └── index.html
└── shared_data/
    ├── input_images/ 
    ├── output_images/
    ├── reference_images/
    └── temp_images/ 
     
```

---


## Requirements

| Component         | Minimum                     | Recommended              |
|-------------------|-----------------------------|--------------------------|
| GPU               | NVIDIA with CUDA support    | 8 GB+ VRAM               |
| RAM               | 24 GB                       | 32 GB+                   |
| CPU               | 8 cores                     | 12+ cores                |
| Storage           | 50 GB (models + images)     | NVMe SSD                 |
| Docker Engine     | 20.10+                      | Latest stable            |
| Docker Compose    | v2 (plugin)                 | —                        |

> **Note**: Running without GPU is **not recommended**.

---

## Environment Setup (Windows / Linux)

> **Run only once**.  
> If Docker + GPU access is already working, skip to [Quick Start](#quick-start).

---

### Windows (with WSL2) – Recommended for Development
---
#### Step 1: Enable Virtualization in BIOS
1. Restart → Enter BIOS (`F2`, `DEL`, `F10`, etc.).  
2. Enable:
   - `Intel VT-x` or `AMD-V`
   - `Virtualization Technology`
3. Save and exit.

---

#### Step 2: Install WSL2
Open **PowerShell** as **Administrator** and run:

```powershell
wsl --install
```

> Installs Ubuntu by default. Restart when prompted. More info: [Install WSL | Microsoft Learn](https://learn.microsoft.com/en-us/windows/wsl/install)

---

#### Step 3: Install Ubuntu (Microsoft Store)
1. Open: [Ubuntu on Microsoft Store](https://aka.ms/wslubuntu)
2. Install → Restart → Launch → Create UNIX user and password.

---

#### Step 4: Install Docker Desktop (Windows)
1. Download: [Docker Desktop for Windows](https://www.docker.com/products/docker-desktop/)
2. Install with default settings.
3. Open Docker Desktop → Enable WSL2 backend.

> Docker Desktop manages WSL integration. **Do not install Docker Engine inside WSL2 if using Docker Desktop**.

---

#### Step 5: (Optional) Install Docker Engine inside WSL2
> Only if **not using Docker Desktop** (e.g., headless server setup)

→ Go to [**Install Docker Engine**](#install-docker-engine), run inside Ubuntu WSL2, then return here.

---

#### Step 6: Install NVIDIA Container Toolkit (GPU Support in WSL2)

> Required for GPU acceleration inside containers.

→ Go to [**NVIDIA Container Toolkit**](#install-nvidia-container-toolkit-gpu-support), run inside **Ubuntu WSL2**, then return here.

---

**Environment ready.** Proceed to [Quick Start](#quick-start).

---

### Linux Native (Ubuntu 22.04+)
---
#### Step 1: Install Docker Engine
→ Go to [**Install Docker Engine**](#install-docker-engine), run in terminal, then return here.

---

#### Step 2: Install NVIDIA Container Toolkit
→ Go to Install [**NVIDIA Container Toolkit**](#install-nvidia-container-toolkit-gpu-support), run in terminal, then return here.

---

**Environment ready.** Proceed to [Quick Start](#quick-start).

---


### Common Setup Steps

#### Install Docker Engine
> **Follow this section on both Windows (inside WSL2) and Linux.**

Following the official Docker instructions
[Install Docker Engine on Ubuntu](https://docs.docker.com/engine/install/ubuntu/) open your terminal (**Ubuntu in WSL2** or **native Linux**) and run:

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install dependencies
sudo apt install -y ca-certificates curl

# Create keyring directory
sudo install -m 0755 -d /etc/apt/keyrings

# Add Docker GPG key
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

# Add Docker repository
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] \
  https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install Docker
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

**Test Docker (Optional)**:

To verify that Docker is installed correctly, run the `hello-world` image:
```bash
sudo docker run hello-world
```

#### Install NVIDIA Container Toolkit (GPU Support)

> **Prerequisite**: Latest NVIDIA drivers installed on **host OS** (Windows or Linux).

Run in your terminal (**Ubuntu in WSL2** or **Native Linux**):

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Add NVIDIA GPG key
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg

# Add repository
curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
  sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
  sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

# (Optional) Enable experimental packages
sed -i -e '/experimental/ s/^#//g' /etc/apt/sources.list.d/nvidia-container-toolkit.list

# Install toolkit
sudo apt update
sudo apt install -y nvidia-container-toolkit
```

**Configure Docker runtime**:
```bash
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
```

**Test GPU access**:
```bash
sudo docker run --rm --gpus all nvidia/cuda:12.4.1-base-ubuntu22.04 nvidia-smi
```
> Should display your GPU (e.g., RTX 3080).

---

## Quick Start

```bash
# 1. Clone repository
git clone https://github.com/BabynovaIA/[REPO_NAME].git
cd [REPO_NAME]

# 2. Copy environment file
cp .env.example .env

# 3. Build and start services
docker compose build
docker compose up -d
```

> API available at: `http://localhost:${FASTAPI_PORT}/docs`

### Script Permissions (Critical First-Time Step)
> **Warning**: Scripts are cloned from Git without execute permissions.
You must set executable bits before running any `.sh` file.

This critical step is required for all **Linux**, **macOS**, and **Windows users (when using WSL)**.

---

**Fix Permissions (Run Once After Clone)**
You must execute the commands below from the root directory of your project.

> **Note**: If you are on Windows, you must run the following commands inside your WSL terminal. to open a new WSL terminal run in powershell:

```powershell
wsl
```
Navigate to the project's root directory within the terminal before running the bash commands below.

```bash
# 1. Set Execute Permissions
chmod +x check_resources.sh
chmod +x comfyui/volumes/scripts/*.sh

# 2. Verify Permissions (Optional)
ls -la comfyui/volumes/scripts/*.sh
```

---

## Initial Configuration

### 1. Environment Variables (`.env`)

```env
FASTAPI_PORT=8000
COMFYUI_PORT=8188
```

> Ports are mapped dynamically: `${VAR:-default}`

### 2. Shared Volume Structure

```
shared_data/
├── input_images/      ← Model face reference images
├── reference_images/  ← Pose reference image
├── temp_images/       ← Temporal images (ComfyUI/temp)
└── output_images/     ← Generated images (ComfyUI/output)
```

---

## FastAPI Endpoints

Interactive docs: `http://localhost:${FASTAPI_PORT}/docs`

---

### `GET /health`

Performs a simple health check on the API.

```bash
curl "http://localhost:${FASTAPI_PORT}/health"
```

**Response:**
```json
{
  "status": "UP"
}
```

### `POST /upload_images`

Upload model and pose reference images.

```bash
curl -X POST "http://localhost:${FASTAPI_PORT}/upload_images" \
  -F "images=@model1.jpg" \
  -F "images=@model2.jpg" \
  -F "reference=@pose_ref.png"
```

- `images`: Multiple model face references
- `reference`: One pose reference image

---

### `POST /clear_images`

Deletes **all** input, reference, and generated images.

```bash
curl -X POST "http://localhost:${FASTAPI_PORT}/clear_images"
```

---

### `GET /list_images`

List all generated images.

```bash
curl "http://localhost:${FASTAPI_PORT}/list_images"
```

**Response:**
```json
{
  "images": ["gen_001.png", "gen_002.jpg"]
}
```

---

## ComfyUI API Endpoints

> **Base URL**: `http://localhost:${COMFYUI_PORT}`  
> **Interactive UI**: `http://localhost:${COMFYUI_PORT}` (Web UI)  
> **API Docs**: [ComfyUI API Reference](https://github.com/comfyanonymous/ComfyUI/blob/master/server.py)

---

### `POST /prompt`

Triggers an image generation workflow by sending a JSON workflow.

```bash
curl -X POST "http://localhost:${COMFYUI_PORT}/prompt" \
  -H "Content-Type: application/json" \
  -d @workflow.json
```

**Response:**
```json
{
  "prompt_id": "a1b2c3d4-5678-90ef-ghij-klmnopqrstuv",
  "number": 1,
  "node_errors": {}
}
```

> Use this `prompt_id` with `/history/{prompt_id}` to check results.

---

### `GET /history/{prompt_id}`

Check the status and output of a submitted prompt.

```bash
curl "http://localhost:${COMFYUI_PORT}/history/{prompt_id}"
```

**Response:**
```json
{
  "a1b2c3d4-5678-90ef-ghij-klmnopqrstuv": {
    "status": "success",
    "outputs": {
      "9": {
        "images": [
          {
            "filename": "ComfyUI_00001_.png",
            "subfolder": "",
            "type": "output"
          }
        ]
      }
    }
  }
}
```

> Images are saved in `shared_data/output_images/` → accessible via FastAPI `/list_images`.

---

### `POST /interrupt`

Interrupts the current running generation.

```bash
curl -X POST "http://localhost:${COMFYUI_PORT}/interrupt"
```

**Response:** `200 OK` if interruption was sent

---

## Using ComfyUI (Optional)

Web UI: **http://localhost:8188**

- Accesses same `shared_data/` volumes.
- Input images available in `/app/input` and `/app/reference`.
- Output saved to `/app/ComfyUI/output`.

> External apps should trigger workflows via **[ComfyUI `/prompt` endpoint](#post-prompt)**.

---

## Docker Commands Cheat Sheet

| Category                     | Action                            | Command                                                                 |
|------------------------------|-----------------------------------|-------------------------------------------------------------------------|
| **Start / Stop**             | Start services                    | `docker compose up -d`                                                  |
|                              | Stop services                     | `docker compose down`                                                   |
|                              | Stop + remove volumes             | `docker compose down --volumes`                                         |
|                              | Restart services                  | `docker compose restart`                                                |
| **Build & Rebuild**          | Rebuild all (no cache)            | `docker compose build --no-cache`                                       |
|                              | Rebuild one service               | `docker compose build --no-cache [fastapi\|comfyui]`                               |
|                              | Rebuild + restart one             | `docker compose up -d --build [fastapi\|comfyui]`                                  |
| **Images**                   | View project images               | `docker compose images`                                                 |
|                              | Remove FastAPI image              | `docker rmi $(docker compose images -q fastapi)`                        |
|                              | Remove ComfyUI image              | `docker rmi $(docker compose images -q comfyui)`                        |
| **Containers**               | View running services             | `docker compose ps`                                                     |
|                              | Enter container shell             | `docker compose exec fastapi /bin/bash`                                 |
|                              | Run one-off command               | `docker compose exec comfyui /app/scripts/script.sh`           |
| **Monitoring**               | View live resource usage          | `docker stats [fastapi\|comfyui]`                                          |
|              | View multiple live resource usage          | `docker stats fastapi comfyui`                                          |
|                              | View logs (all)                   | `docker compose logs -f`                                                |
|                              | View logs (one service)           | `docker compose logs -f comfyui`                                        |
| **Cleanup**                  | Clean only volumes                | `docker compose down --volumes`                                         |
|                              | Nuke everything (nuclear)         | `docker compose down --rmi all --volumes --remove-orphans`              |

---

## Resource Management
Efficient resource management is critical when running GPU-intensive AI workloads in Docker. This section covers monitoring, optimization, memory handling, and safe cleanup procedures.

### Real-Time Monitoring
1. **Container Resource Usage**
```bash
docker stats fastapi comfyui
```

> Displays CPU, memory, network, and block I/O in real time.

2. **GPU Utilization (Host Level)**
```powershell
# Windows PowerShell (looping)
while ($true) { cls; nvidia-smi; Start-Sleep -Seconds 1 }
```

```bash
# Linux / WSL2 (continuous)
watch -n 1 nvidia-smi
```
> Monitor VRAM usage, temperature, and process list (`comfyui` should appear under Python).

A custom script has been created for consolidated resource monitoring and basic GPU status checks within the environment.

> **Note**: You must execute this command from the **root directory** of your project.

```bash
# Custom Resourse monitor
./check_resources.sh
```

3. **Inside ComfyUI Container (Advanced)**
```bash
docker compose exec comfyui nvidia-smi
docker compose exec comfyui gpustat -cp
docker compose exec comfyui watch -n 1 gpustat
```

> Use `gpustat` for cleaner GPU process visualization (pre-installed in ComfyUI image).

---

### Safe Docker Cleanup

> **Warning**: Incorrect cleanup can delete critical data. Always verify paths.

1. **Stop Services First**
```bash
docker compose down
```
---

2. **Prune Unused Resources**
```bash
docker system prune -a --volumes --force
```
---

3. **Selective Volume Cleanup (Recommended)**

Never run global prune in production. Instead:
```bash
# List all volumes
docker volume ls

# Inspect your project volumes
docker volume inspect $(docker compose config --volumes | grep -v "local")

# Remove only project-specific volumes
docker compose down --volumes
```
---

4. **WSL2-Specific Disk Optimization (Windows)**

Docker Desktop stores WSL2 disks in:
```text
%LOCALAPPDATA%\Packages\...\LocalState\ext4.vhdx
```
Docker Desktop stores its legacy WSL2 data disks in the following location (common in older versions):
```text
%LOCALAPPDATA%\Docker\wsl\disk\docker_data.vhdx
```
**Compact the virtual disk** after heavy container and image cleanup to reclaim significant unused space on your host drive.

```powershell
# 1. Shut down WSL
wsl --shutdown

# 2. Define the path to the Docker Desktop VHDX file
$vhdxPath = "$env:LOCALAPPDATA\Packages\...\LocalState\ext4.vhdx"

# Verify path exists before running
if (Test-Path $vhdxPath) {
    Optimize-VHD -Path $vhdxPath -Mode Full
    Write-Host "VHDX compacted successfully."
} else {
    Write-Warning "VHDX not found at: $vhdxPath"
}
```
```powershell
# 1. Shut down WSL
wsl --shutdown

# 2. Define the path to the legacy Docker Desktop VHDX file
$vhdxPath = "$env:LOCALAPPDATA\Docker\wsl\disk\docker_data.vhdx"

# Verify path exists before running
if (Test-Path $vhdxPath) {    
    Optimize-VHD -Path $vhdxPath -Mode Full
    Write-Host "Docker VHDX compacted successfully." 
} else {
    Write-Warning "Legacy VHDX not found at: $vhdxPath"
}
```
> Always verify `$vhdxPath` exists before running `Optimize-VHD`.
---
5. **Manual Volume Backup and Restore**

**Backup**
```bash
# Backup models
tar -czf models_backup_$(date +%Y%m%d).tar.gz -C comfyui/volumes/models .

# Backup nodes
tar -czf custom_nodes_backup_$(date +%Y%m%d).tar.gz -C comfyui/volumes/custom_nodes .
```

**Restore**
```bash
# Restore models
tar -xzf models_backup.tar.gz -C comfyui/volumes/

# Restore nodes
tar -xzf custom_nodes_backup.tar.gz -C comfyui/volumes/
```
> **Warning**: Replace models_backup.tar.gz and custom_nodes_backup.tar.gz for the real file name
---

### VRAM Leak Prevention
ComfyUI may hold onto GPU memory between runs.

**Force Cleanup Inside Container**
```bash
docker compose exec comfyui python -c "
import gc, torch
torch.cuda.empty_cache()
gc.collect()
print('VRAM cache cleared')
"
```
**Restart ComfyUI Service**
```bash
docker compose restart comfyui
```

## License

**Internal Project** | Private Use Only | No Public License

---