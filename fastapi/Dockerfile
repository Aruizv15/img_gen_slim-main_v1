import os
import shutil
from huggingface_hub import hf_hub_download, list_repo_files

HF_TOKEN = os.getenv("HF_TOKEN", "")
repo = 'novafem54/batchapp-models'
extensions = ('.safetensors', '.pt', '.pth', '.onnx', '.bin')
base_dir = '/runpod-volume/models'

files = [f for f in list_repo_files(repo, token=HF_TOKEN) if f.endswith(extensions)]
print(f'Descargando {len(files)} modelos...', flush=True)

for f in files:
    print(f'Descargando: {f}', flush=True)

    # Quitar el prefijo 'volumes/models/' de la ruta
    if f.startswith('volumes/models/'):
        relative_path = f[len('volumes/models/'):]
    else:
        relative_path = f

    local_path = os.path.join(base_dir, relative_path)
    os.makedirs(os.path.dirname(local_path), exist_ok=True)

    # Descargar a carpeta temporal
    downloaded = hf_hub_download(
        repo_id=repo,
        filename=f,
        local_dir='/tmp/hf_download',
        local_dir_use_symlinks=False,
        token=HF_TOKEN
    )

    # Mover al lugar correcto
    shutil.move(downloaded, local_path)
    print(f'OK: {local_path}', flush=True)

print('Todos los modelos descargados', flush=True)
