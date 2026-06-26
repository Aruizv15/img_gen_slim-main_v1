import os
from huggingface_hub import hf_hub_download, list_repo_files

HF_TOKEN = os.getenv("HF_TOKEN")
repo = 'novafem54/batchapp-models'
extensions = ('.safetensors', '.pt', '.pth', '.onnx', '.bin')

files = [f for f in list_repo_files(repo, token=HF_TOKEN) if f.endswith(extensions)]
print(f'Descargando {len(files)} modelos...', flush=True)

for f in files:
    print(f'Descargando: {f}', flush=True)
    os.makedirs(os.path.dirname(f'/workspace/ComfyUI_app/models/{f}'), exist_ok=True)
    hf_hub_download(repo_id=repo, filename=f, local_dir='/workspace/ComfyUI_app/models', token=HF_TOKEN)
    print(f'OK: {f}', flush=True)

print('Todos los modelos descargados', flush=True)
