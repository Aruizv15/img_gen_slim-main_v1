FROM runpod/pytorch:2.1.0-py3.10-cuda11.8.0-devel-ubuntu22.04

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        curl \
        git \
        libgl1 \
        libglib2.0-0 && \
    rm -rf /var/lib/apt/lists/*

# ------------------------------------------------------------------
# Torch CUDA 11.8
# ------------------------------------------------------------------

RUN pip install --no-cache-dir --force-reinstall \
    torch==2.1.0+cu118 \
    torchvision==0.16.0+cu118 \
    torchaudio==2.1.0+cu118 \
    --index-url https://download.pytorch.org/whl/cu118

RUN python -c "import torch; assert torch.version.cuda.startswith('11.8'); print('CUDA OK:', torch.version.cuda)"

# ------------------------------------------------------------------
# App
# ------------------------------------------------------------------

WORKDIR /app

RUN mkdir -p \
    /app/templates \
    /app/static/css \
    /app/static/js \
    /app/shared_data/input_images \
    /app/shared_data/output_images \
    /app/shared_data/reference_images \
    /app/shared_data/temp_images \
    /app/workflows

# ------------------------------------------------------------------
# ComfyUI
# ------------------------------------------------------------------

RUN git clone https://github.com/comfyanonymous/ComfyUI.git /workspace/ComfyUI_app && \
    cd /workspace/ComfyUI_app && \
    git checkout tags/v0.3.10

RUN grep -vE "^torch|^torchvision|^torchaudio" \
    /workspace/ComfyUI_app/requirements.txt > /tmp/comfy_reqs.txt && \
    pip install --no-cache-dir -r /tmp/comfy_reqs.txt

# ------------------------------------------------------------------
# Dependencias necesarias para Impact Pack
# ------------------------------------------------------------------

RUN pip install --no-cache-dir \
    torchsde \
    ultralytics \
    segment-anything \
    pycocotools \
    opencv-python \
    scikit-image \
    timm \
    onnxruntime

# ------------------------------------------------------------------
# FastAPI
# ------------------------------------------------------------------

COPY requirements.txt /app/

RUN grep -vE "^torch|^torchvision|^torchaudio" \
    /app/requirements.txt > /tmp/app_reqs.txt && \
    pip install --no-cache-dir -r /tmp/app_reqs.txt

# ------------------------------------------------------------------
# ImgGenScript
# ------------------------------------------------------------------

COPY ImgGenScript/ /workspace/ImgGenScript/

RUN grep -vE "^torch|^torchvision|^torchaudio" \
    /workspace/ImgGenScript/backend/requirements.txt > /tmp/imggen_reqs.txt && \
    pip install --no-cache-dir -r /tmp/imggen_reqs.txt

# ------------------------------------------------------------------
# Custom Nodes
# ------------------------------------------------------------------

RUN cd /workspace/ComfyUI_app/custom_nodes && \
    git clone https://github.com/crystian/ComfyUI-Crystools.git && \
    git clone https://github.com/cubiq/ComfyUI_essentials.git && \
    git clone https://github.com/Fannovel16/comfyui_controlnet_aux.git && \
    git clone https://github.com/cubiq/ComfyUI_IPAdapter_plus.git && \
    git clone https://github.com/ltdrdata/ComfyUI-Impact-Pack.git && \
    git clone https://github.com/ltdrdata/ComfyUI-Inspire-Pack.git && \
    git clone https://github.com/RockOfFire/ComfyUI_Comfyroll_CustomNodes.git && \
    git clone https://github.com/yolain/ComfyUI-Easy-Use.git && \
    git clone https://github.com/ChrisColeTech/ComfyUI-Elegant-Resource-Monitor.git && \
    git clone https://github.com/ShmuelRonen/ComfyUI-FreeMemory.git && \
    git clone https://github.com/ltdrdata/ComfyUI-Impact-Subpack.git && \
    git clone https://github.com/cubiq/ComfyUI_FaceAnalysis.git && \
    git clone https://github.com/sipherxyz/comfyui-art-venture.git

# ------------------------------------------------------------------
# Verificar que Impact Pack existe
# ------------------------------------------------------------------

RUN ls -la /workspace/ComfyUI_app/custom_nodes && \
    ls -la /workspace/ComfyUI_app/custom_nodes/ComfyUI-Impact-Pack

# ------------------------------------------------------------------
# Instalar requirements de TODOS los custom nodes
# ------------------------------------------------------------------

RUN for dir in /workspace/ComfyUI_app/custom_nodes/*/; do \
    if [ -f "$dir/requirements.txt" ]; then \
        echo "============================="; \
        echo "Installing: $dir"; \
        grep -vE "^torch|^torchvision|^torchaudio" "$dir/requirements.txt" > /tmp/node_reqs.txt; \
        pip install --no-cache-dir -r /tmp/node_reqs.txt; \
    fi; \
done

# ------------------------------------------------------------------
# Restaurar Torch
# ------------------------------------------------------------------

RUN pip install --no-cache-dir --force-reinstall \
    torch==2.1.0+cu118 \
    torchvision==0.16.0+cu118 \
    torchaudio==2.1.0+cu118 \
    --index-url https://download.pytorch.org/whl/cu118

# ------------------------------------------------------------------
# Modelos
# ------------------------------------------------------------------

COPY download_models.py /app/

# ------------------------------------------------------------------
# App
# ------------------------------------------------------------------

COPY main.py /app/
COPY handler.py /app/
COPY test_input.json /app/test_input.json
COPY templates/ /app/templates/
COPY static/ /app/static/

# ------------------------------------------------------------------
# Verificaciones
# ------------------------------------------------------------------

RUN python -c "import torch; print(torch.__version__, torch.version.cuda)"

RUN python - <<'PY'
import os
print("Impact Pack:", os.path.isdir("/workspace/ComfyUI_app/custom_nodes/ComfyUI-Impact-Pack"))
PY

EXPOSE 8000

CMD ["python", "/app/handler.py"]
