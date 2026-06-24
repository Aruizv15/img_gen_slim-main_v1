import sys
import time
import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
BACKEND_DIR = PROJECT_ROOT / "backend"

# Add the 'backend' directory to sys.path to allow relative imports.
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from backend.src.config.settings import get_settings, Settings
    from backend.src.utils import organize_approved_images
except ImportError as e:
    print(f"Error importing modules: {e}")
    print(f"PROJECT_ROOT: {PROJECT_ROOT}")
    print(f"Backend folder exists?: {(PROJECT_ROOT / 'backend').exists()}")
    print(f"sys.path[0]: {sys.path[0]}")
    sys.exit(1)


def run_organizer_loop(settings: Settings):
    """
    Runs an infinite loop that organizes approved images at regular intervals.

    Args:
        settings (Settings): The application's configuration instance.
    """
    print("Press Ctrl+C to quit.")
    try:
        while True:
            now = datetime.datetime.now()
            print(f"Last updated: {now.strftime('%Y-%m-%d %H:%M:%S')}", end='\r')

            organize_approved_images(settings.images_dir, settings.approved_dir)

            time.sleep(settings.approved_scan_interval * 60)
    except KeyboardInterrupt:
        print("\n\nScript stopped by user (Ctrl+C).")
    except Exception as e:
        print(f"\n\nAn unexpected error occurred: {e}")


def main():
    """
    Loads the configuration and starts the organization loop.
    """
    try:
        settings = get_settings()
        run_organizer_loop(settings)
    except FileNotFoundError as e:
        print(f"Error: Could not load configuration. {e}")
    except Exception as e:
        print(f"A critical error occurred while starting the script: {e}")


if __name__ == "__main__":
    main()