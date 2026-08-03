FROM runpod/pytorch:2.1.0-py3.10-cuda11.8.0-devel-ubuntu22.04
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        curl \
        git \
        libgl1 \
        libglib2.0-0 \
        libgles2 \
        libegl1 \
        libx11-6 && \
    rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir --force-reinstall \
    torch==2.1.0+cu118 \
    torchvision==0.16.0+cu118 \
    torchaudio==2.1.0+cu118 \
    --index-url https://download.pytorch.org/whl/cu118
RUN python -c "import torch; assert torch.version.cuda.startswith('11.8'); print('CUDA OK:', torch.version.cuda)"
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
RUN git clone https://github.com/comfyanonymous/ComfyUI.git /workspace/ComfyUI_app && \
    cd /workspace/ComfyUI_app && \
    git checkout tags/v0.3.28
RUN grep -vE "^torch|^torchvision|^torchaudio" \
    /workspace/ComfyUI_app/requirements.txt > /tmp/comfy_reqs.txt && \
    pip install --no-cache-dir -r /tmp/comfy_reqs.txt
RUN pip install --no-cache-dir \
    torchsde \
    ultralytics \
    segment-anything \
    pycocotools \
    opencv-python \
    scikit-image \
    timm \
    onnxruntime \
    supervision \
    dill
COPY requirements.txt /app/
RUN grep -vE "^torch|^torchvision|^torchaudio" \
    /app/requirements.txt > /tmp/app_reqs.txt && \
    pip install --no-cache-dir -r /tmp/app_reqs.txt
COPY ImgGenScript/ /workspace/ImgGenScript/
RUN grep -vE "^torch|^torchvision|^torchaudio" \
    /workspace/ImgGenScript/backend/requirements.txt > /tmp/imggen_reqs.txt && \
    pip install --no-cache-dir -r /tmp/imggen_reqs.txt
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
RUN for dir in /workspace/ComfyUI_app/custom_nodes/*/; do \
    if [ -f "$dir/requirements.txt" ]; then \
        echo "============================="; \
        echo "Installing: $dir"; \
        grep -vE "^torch|^torchvision|^torchaudio" "$dir/requirements.txt" > /tmp/node_reqs.txt; \
        pip install --no-cache-dir -r /tmp/node_reqs.txt || true; \
    fi; \
done
RUN pip install --no-cache-dir --force-reinstall \
    torch==2.1.0+cu118 \
    torchvision==0.16.0+cu118 \
    torchaudio==2.1.0+cu118 \
    --index-url https://download.pytorch.org/whl/cu118
COPY download_models.py /app/
COPY main.py /app/
COPY auth.py /app/
COPY handler.py /app/
COPY test_input.json /app/test_input.json
COPY templates/ /app/templates/
COPY static/ /app/static/
RUN python -c "import torch; print(torch.__version__, torch.version.cuda)"

# --- Fix adicional: forzar transformers==4.41.2 ---
# Igual que con numpy: algun custom_node reinstala 'transformers' sin fijar
# version, y las versiones nuevas de transformers exigen torch>=2.4 para
# reconocer PyTorch como backend disponible. Como aqui usamos torch==2.1.0
# (por compatibilidad con CUDA 11.8), transformers "deshabilita" PyTorch
# silenciosamente, rompiendo MeshGraphormer (Hands Refiner) con el error
# "modeling_bert requires the PyTorch library but it was not found".
# IMPORTANTE: esto va ANTES del fix de numpy, porque instalar transformers
# arrastra su propia version de numpy (sin tope superior) como dependencia,
# lo que rompe el pin de numpy si se hace despues.
RUN pip install --no-cache-dir --force-reinstall transformers==4.41.2

# --- Fix final: forzar NumPy 1.26.4 como VERDADERA ULTIMA instalacion ---
# Varios custom_nodes instalados arriba (y ahora tambien transformers)
# reinstalan numpy>=2, rompiendo la compatibilidad con torch==2.1.0
# (compilado contra NumPy 1.x). Esta linea tiene que ser la ultima palabra
# del build para garantizar que nada la sobreescriba despues.
RUN pip install --no-cache-dir --force-reinstall numpy==1.26.4

RUN python -c "import numpy, torch; print('NumPy:', numpy.__version__); print('Torch:', torch.__version__); import torch; torch.tensor([1,2,3]).numpy()" 
RUN python -c "from transformers.utils import is_torch_available; assert is_torch_available(), 'transformers no reconoce torch como backend disponible'; print('transformers reconoce PyTorch correctamente')"

EXPOSE 8000
CMD ["python", "/app/handler.py"]
