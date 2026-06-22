FROM nvidia/cuda:12.1.1-cudnn8-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    python3 python3-pip \
    git git-lfs \
    ffmpeg libgl1 libglib2.0-0 libsm6 libxext6 libgl1-mesa-glx \
    curl wget unzip \
    build-essential \
    cmake \
    python3-dev \
    libboost-all-dev \
    libopenblas-dev \
    libx11-dev \
    pkg-config \
    libcairo2-dev \
    && rm -rf /var/lib/apt/lists/* \
    && git lfs install \
    && ln -s /usr/bin/python3 /usr/bin/python

RUN pip install watchdog

WORKDIR /app

RUN git clone https://github.com/comfyanonymous/ComfyUI.git
WORKDIR /app/ComfyUI

RUN git checkout v0.3.66

RUN mkdir -p /app/ComfyUI/custom_nodes \
    /app/ComfyUI/models/checkpoints \
    /app/ComfyUI/models/clip_vision \
    /app/ComfyUI/models/controlnet \
    /app/ComfyUI/models/ipadapter \
    /app/ComfyUI/models/loras \
    /app/ComfyUI/models/vae \
    /app/ComfyUI/outputs \
    /app/input \
    /app/reference\
    /app/scripts
    
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

COPY requirements.txt /app/requirements.txt
RUN pip install -r /app/requirements.txt

EXPOSE 8188 8288

WORKDIR /app
# CMD ["python", "launcher/comfyui_launcher.py"]
CMD ["watchmedo", "auto-restart", "--directory=/app/launcher", "--pattern=*.py", "--recursive", "--", "python", "launcher/comfyui_launcher.py"]

RUN apt-get clean && rm -rf /tmp/*