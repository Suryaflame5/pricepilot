"""Standalone entry point for the packaged API executable."""

import sys
import os

# For PyInstaller, add the extracted directory to path
if getattr(sys, 'frozen', False):
    # Running in a PyInstaller bundle
    base_path = sys._MEIPASS
else:
    # Running in normal Python environment
    base_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Add all necessary directories to path
for directory in ['packages', 'services', 'ml', 'infrastructure']:
    dir_path = os.path.join(base_path, directory)
    if dir_path not in sys.path:
        sys.path.insert(0, dir_path)

# Add base path to root level imports
if base_path not in sys.path:
    sys.path.insert(0, base_path)

from api.main import app
import uvicorn

def main():
    """Run the API server."""
    print("Starting PricePilot API server...")
    print("Server will be available at http://localhost:8000")
    print(f"Base path: {base_path}")
    print(f"Python path: {sys.path[:3]}")
    
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8000,
        log_level="info"
    )

if __name__ == "__main__":
    main()