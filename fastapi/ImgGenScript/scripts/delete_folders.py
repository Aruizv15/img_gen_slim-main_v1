import os
import re
import shutil
import sys
import stat
import time
from pathlib import Path
from typing import List

BASE_DIR = Path("files/images/FINALIZADAS")
DRY_RUN = False
RETRY_COUNT = 3
RETRY_DELAY = 1

def is_ovod_folder(folder_name: str) -> bool:
    return bool(re.match(r"^OVOD\d{5,}$", folder_name))


def force_remove_readonly(func, path, exc_info):
    """Callback para shutil.rmtree que quita el atributo solo-lectura antes de reintentar"""
    os.chmod(path, stat.S_IWRITE)
    func(path)


def delete_folder_with_retry(folder_path: Path, dry_run: bool) -> bool:
    """Intenta eliminar la carpeta con reintentos y manejo de permisos"""
    if dry_run:
        print(f"   [DRY-RUN] Would delete: {folder_path}")
        return True

    for attempt in range(1, RETRY_COUNT + 1):
        try:
            # Primero intenta eliminar quitando atributos de solo lectura
            shutil.rmtree(folder_path, onerror=force_remove_readonly)
            print(f"   Successfully deleted: {folder_path}")
            return True

        except PermissionError as e:
            print(f"   Attempt {attempt}/{RETRY_COUNT} failed (Access denied): {folder_path}")
            if attempt < RETRY_COUNT:
                time.sleep(RETRY_DELAY)
            else:
                print(f"   Failed after {RETRY_COUNT} attempts: {folder_path}")
                print(f"   Error: {e}")
                return False

        except Exception as e:
            print(f"   Unexpected error deleting {folder_path}: {e}")
            return False

    return False


def delete_fullbody_and_portrait(root_folder: Path, dry_run: bool = False):
    if not root_folder.exists():
        print(f"Error: Base directory does not exist: {root_folder}")
        return

    ovoid_folders = [
        p for p in root_folder.iterdir()
        if p.is_dir() and is_ovod_folder(p.name)
    ]

    print(f"Found {len(ovoid_folders)} OVOD folders\n")

    deleted_count = 0
    failed_count = 0

    for folder in ovoid_folders:
        print(f"Processing → {folder.name}")

        for target in ["fullbody", "portrait"]:
            target_path = folder / target

            if target_path.exists():
                success = delete_folder_with_retry(target_path, dry_run)
                if success and not dry_run:
                    deleted_count += 1
                elif not success and not dry_run:
                    failed_count += 1
            else:
                print(f"   [INFO] '{target}' does not exist → skipped")

        print("")

    # Resumen final
    print("=" * 60)
    if dry_run:
        print("DRY-RUN COMPLETED – No folders were actually deleted")
    else:
        print(f"OPERATION COMPLETED")
        print(f"   Successfully deleted folders: {deleted_count}")
        print(f"   Failed to delete folders:     {failed_count}")
    print("=" * 60)


def main():
    print("=== OVOD fullbody/portrait Cleaner (Windows Edition) ===\n")
    print(f"Base directory: {BASE_DIR.resolve()}")
    print(f"Dry-run mode: {'YES' if DRY_RUN else 'NO'}\n")

    if DRY_RUN:
        print("Running in simulation mode – nothing will be deleted.\n")

    confirm = input("Continue? (y/N): ").strip().lower()
    if confirm != "y":
        print("Operation cancelled.")
        return

    delete_fullbody_and_portrait(BASE_DIR, dry_run=DRY_RUN)


if __name__ == "__main__":
    main()