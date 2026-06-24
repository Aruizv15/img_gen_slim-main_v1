import sys
import os

project_root = os.path.abspath(os.path.join(os.getcwd(), "backend"))

if project_root not in sys.path:
    sys.path.insert(0, project_root)

from backend.app.app import BatchApp
if __name__ == "__main__":
    app = BatchApp()
    app.run(inline=True)