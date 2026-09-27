#!/usr/bin/env python3
"""Build script for packaging the Python backend as an executable."""

import os
import sys
import subprocess
import shutil

def main():
    print("Building Python backend executable...")
    
    # Check if we're in a virtual environment
    if sys.prefix == sys.base_prefix:
        print("Warning: Not running in a virtual environment")
        print("Please activate your virtual environment first:")
        print("  .venv\\Scripts\\activate")
        sys.exit(1)
    
    # Install PyInstaller if not already installed
    try:
        import PyInstaller
        print(f"PyInstaller already installed: {PyInstaller.__version__}")
    except ImportError:
        print("Installing PyInstaller...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])
    
    # Clean previous builds
    if os.path.exists("build"):
        shutil.rmtree("build")
    if os.path.exists("dist"):
        shutil.rmtree("dist")
    
    # Build the executable
    print("Running PyInstaller...")
    subprocess.check_call([
        sys.executable, "-m", "PyInstaller",
        "build_backend.spec",
        "--clean"
    ])
    
    # Create the backend-dist directory structure
    backend_dist = "backend-dist"
    if os.path.exists(backend_dist):
        shutil.rmtree(backend_dist)
    
    os.makedirs(backend_dist, exist_ok=True)
    
    # Copy the executable to backend-dist
    if os.path.exists("dist/api.exe"):
        shutil.copy("dist/api.exe", f"{backend_dist}/api.exe")
        print(f"Backend executable created: {backend_dist}/api.exe")
    else:
        print("Error: api.exe not found in dist/")
        sys.exit(1)
    
    # Copy necessary configuration files
    if os.path.exists(".env.example"):
        shutil.copy(".env.example", f"{backend_dist}/.env.example")
    
    if os.path.exists("docker-compose.yml"):
        shutil.copy("docker-compose.yml", f"{backend_dist}/docker-compose.yml")
    
    print(f"\nBackend build complete! Executable location: {backend_dist}/api.exe")
    print("This directory will be included in the Electron build.")

if __name__ == "__main__":
    main()