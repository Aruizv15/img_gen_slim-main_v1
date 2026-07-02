FROM runpod/pytorch:2.1.0-py3.10-cuda11.8.0-devel-ubuntu22.04
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl git libgl1 libglib2.0-0 && \
    rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir --force-reinstall \
        torch==2.1.0+cu118 \
        torchvision==0.16.0+cu118 \
        torchaudio==2.1.0+cu118 \
        --index-url https://download.pytorch.org/whl/cu118
RUN python -c "import torch; assert torch.version.cuda.startswith('11.8'), f'CUDA INCORRECTO: {torch.version.cuda}'; print('OK cu118')"
WORKDIR /app
RUN mkdir -p /app/templates /app/static/css /app/static/js \
    /app/shared_data/input_images /app/shared_data/output_images \
    /app/shared_data/reference_images /app/shared_data/temp_images \
    /app/workflows
RUN git clone https://github.com/comfyanonymous/ComfyUI.git /workspace/ComfyUI_app && \
    cd /workspace/ComfyUI_app && \
    git checkout tags/v0.3.10
RUN grep -vE "^torch|^torchvision|^torchaudio" \
        /workspace/ComfyUI_app/requirements.txt > /tmp/comfy_reqs.txt && \
    pip install --no-cache-dir -r /tmp/comfy_reqs.txt && \
    pip install --no-cache-dir torchsde
COPY requirements.txt /app/
RUN grep -vE "^torch|^torchvision|^torchaudio" \
        /app/requirements.txt > /tmp/app_reqs.txt && \
    pip install --no-cache-dir -r /tmp/app_reqs.txt
COPY ImgGenScript/ /workspace/ImgGenScript/
RUN grep -vE "^torch|^torchvision|^torchaudio" \
        /workspace/ImgGenScript/backend/requirements.txt > /tmp/imggen_reqs.txt && \
    pip install --no-cache-dir -r /tmp/imggen_reqs.txt
    
RUN cd /workspace/ComfyUI_app/custom_nodes && \
    git clone https://github.com/crystian/ComfyUI-Crystools.git || true && \
    git clone https://github.com/cubiq/ComfyUI_essentials.git || true && \
    git clone https://github.com/Fannovel16/comfyui_controlnet_aux.git || true && \
    git clone https://github.com/cubiq/ComfyUI_IPAdapter_plus.git || true && \
    git clone https://github.com/ltdrdata/ComfyUI-Impact-Pack.git || true && \
    git clone https://github.com/ltdrdata/ComfyUI-Inspire-Pack.git || true && \
    git clone https://github.com/RockOfFire/ComfyUI_Comfyroll_CustomNodes.git || true && \
    git clone https://github.com/yolain/ComfyUI-Easy-Use.git || true && \
    git clone https://github.com/ChrisColeTech/ComfyUI-Elegant-Resource-Monitor.git || true && \
    git clone https://github.com/ShmuelRonen/ComfyUI-FreeMemory.git || true && \
    git clone https://github.com/ltdrdata/ComfyUI-Impact-Subpack.git || true && \
    git clone https://github.com/cubiq/ComfyUI_FaceAnalysis.git || true && \
    git clone https://github.com/sipherxyz/comfyui-art-venture.git || true
    
COPY download_models.py /tmp/download_models.py
ARG HF_TOKEN
ENV HF_TOKEN=${HF_TOKEN}
RUN pip install --no-cache-dir "huggingface_hub>=0.20" && \
    python /tmp/download_models.py
COPY main.py /app/
COPY handler.py /app/
COPY test_input.json /app/test_input.json
COPY templates/ /app/templates/
COPY static/ /app/static/
RUN python -c "import torch; assert torch.version.cuda.startswith('11.8'), f'torch sobreescrito!'; print('OK torch intacto')"
EXPOSE 8000
CMD ["python", "/app/handler.py"]
