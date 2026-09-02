import os
from huggingface_hub import hf_hub_download, list_repo_files

HF_TOKEN = os.getenv("HF_TOKEN", "")
repo = 'novafem54/batchapp-models'
extensions = ('.safetensors', '.pt', '.pth', '.onnx', '.bin', '.task')

files = [f for f in list_repo_files(repo, token=HF_TOKEN) if f.endswith(extensions)]
print(f'Descargando {len(files)} modelos...', flush=True)

for f in files:
    print(f'Descargando: {f}', flush=True)

    # Determinar destino según el prefijo
    if f.startswith('volumes/models/'):
        # Modelos principales van al Network Volume
        relative_path = f[len('volumes/models/'):]
        local_path = os.path.join('/runpod-volume/models', relative_path)
    elif f.startswith('volumes/custom_nodes/'):
        # Archivos de custom nodes van al workspace
        relative_path = f[len('volumes/custom_nodes/'):]
        local_path = os.path.join('/workspace/ComfyUI_app/custom_nodes', relative_path)
    else:
        # Cualquier otro archivo va al volumen
        local_path = os.path.join('/runpod-volume/models', f)

    # Verificar si ya existe
    if os.path.exists(local_path):
        print(f'Ya existe: {local_path}', flush=True)
        continue

    os.makedirs(os.path.dirname(local_path), exist_ok=True)

    # Descargar directamente al destino
    downloaded = hf_hub_download(
        repo_id=repo,
        filename=f,
        local_dir='/tmp/hf_download',
        token=HF_TOKEN
    )

    # Copiar al destino final
    import shutil
    shutil.copy2(downloaded, local_path)
    os.remove(downloaded)
    print(f'OK: {local_path}', flush=True)

print('Todos los modelos descargados', flush=True)
