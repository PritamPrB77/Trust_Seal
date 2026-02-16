"""
run.py - FastAPI Application Runner

This script is used to start the FastAPI application with proper Python path configuration.

Why this fixes the 'Error loading ASGI app. Could not import module "app.main"' error:
1. The error occurs because Python can't find the 'app' module when uvicorn tries to import it.
2. This script adds the project's root directory to Python's module search path (sys.path).
3. By adding the project root to sys.path, Python can now locate the 'app' package.
4. The uvicorn server is then started with the correct module path.

Usage:
    python run.py
"""

import sys
from pathlib import Path
import uvicorn

# Get the project's root directory (where this run.py file is located)
project_root = Path(__file__).parent.absolute()
print(f"Project root: {project_root}")

# Add the project root to Python's module search path
# This ensures that 'app' can be found when importing
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
    print(f"Added to Python path: {project_root}")

if __name__ == "__main__":
    # Print the Python path for debugging
    print("\nPython path:")
    for p in sys.path:
        print(f"- {p}")
    
    # Start the FastAPI application
    print("\nStarting FastAPI application...")
    print("Access the API documentation at: http://127.0.0.1:8000/docs\n")
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_dirs=[str(project_root / "app")]  # Watch for changes in app directory
    )
