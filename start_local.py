#!/usr/bin/env python3
"""Local development startup script - no Docker required."""

import subprocess
import sys
import os
from pathlib import Path

def main():
    """Start the local development environment."""
    print("Starting PricePilot local development environment...")
    print("Using embedded SQLite database - no external dependencies required.")
    
    # Ensure we're in the project root
    project_root = Path(__file__).parent
    os.chdir(project_root)
    
    # Install dependencies if needed
    try:
        import uvicorn
        import fastapi
    except ImportError:
        print("Installing dependencies...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-e", ".[ml,dev]"])
    
    # Initialize database
    print("Initializing SQLite database...")
    subprocess.check_call([sys.executable, "-c", """
import asyncio
from packages.database.session import create_engine, init_db
from services.api.config import settings

async def setup():
    engine = create_engine(settings.database_url)
    await init_db(engine)
    print("Database initialized successfully!")

asyncio.run(setup())
"""])
    
    # Start the API server
    print("Starting API server on http://localhost:8000")
    print("API documentation available at http://localhost:8000/docs")
    print("Press Ctrl+C to stop")
    
    subprocess.run([
        sys.executable, "-m", "uvicorn", 
        "api.main:app",
        "--host", "127.0.0.1", 
        "--port", "8000",
        "--reload",
        "--app-dir", "services"
    ])

if __name__ == "__main__":
    main()