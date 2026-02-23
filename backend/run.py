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
import subprocess
import os
import socket
from pathlib import Path
import uvicorn
from sqlalchemy.engine.url import make_url
from app.core.config import settings

# Get the project's root directory (where this run.py file is located)
project_root = Path(__file__).parent.absolute()
print(f"Project root: {project_root}")

# Prefer the project virtual environment automatically.
venv_python = project_root / ".venv" / "Scripts" / "python.exe"
current_python = Path(sys.executable).resolve()
if venv_python.exists():
    target_python = venv_python.resolve()
    if current_python != target_python:
        print(f"Switching interpreter to project venv: {target_python}")
        result = subprocess.run([str(target_python), str(Path(__file__).resolve()), *sys.argv[1:]])
        sys.exit(result.returncode)

# Add the project root to Python's module search path
# This ensures that 'app' can be found when importing
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
    print(f"Added to Python path: {project_root}")


def _safe_database_target(url: str) -> str:
    try:
        parsed = make_url(url)
        if parsed.drivername.startswith("sqlite"):
            return f"{parsed.drivername}:///{parsed.database or ''}"
        host = parsed.host or "unknown-host"
        port = parsed.port or "unknown-port"
        database = parsed.database or "unknown-db"
        return f"{parsed.drivername}://{host}:{port}/{database}"
    except Exception:
        return "<unable-to-parse-database-url>"


def _is_port_in_use(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.25)
        return sock.connect_ex((host, port)) == 0


def _choose_port(preferred_port: int) -> int:
    if not _is_port_in_use("127.0.0.1", preferred_port):
        return preferred_port
    for candidate in range(preferred_port + 1, preferred_port + 11):
        if not _is_port_in_use("127.0.0.1", candidate):
            return candidate
    return preferred_port

if __name__ == "__main__":
    # Print the Python path for debugging
    print("\nPython path:")
    for p in sys.path:
        print(f"- {p}")
    
    # Start the FastAPI application
    print("\nStarting FastAPI application...")
    print(f"Database target: {_safe_database_target(settings.DATABASE_URL)}")
    preferred_port = int(os.getenv("UVICORN_PORT", "8001"))
    reload_enabled = os.getenv("UVICORN_RELOAD", "false").lower() in {"1", "true", "yes"}
    chosen_port = _choose_port(preferred_port) if not reload_enabled else preferred_port
    if chosen_port != preferred_port:
        print(
            f"Port {preferred_port} is busy. Falling back to port {chosen_port}. "
            "Set UVICORN_PORT to pin a port."
        )
    print(f"Access the API documentation at: http://127.0.0.1:{chosen_port}/docs\n")

    uvicorn_kwargs = {
        "app": "app.main:app",
        "host": "0.0.0.0",
        "port": chosen_port,
        "reload": reload_enabled,
    }
    if reload_enabled:
        uvicorn_kwargs["reload_dirs"] = [str(project_root / "app")]  # Watch for changes in app directory

    uvicorn.run(**uvicorn_kwargs)
