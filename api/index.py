import sys
import os
import traceback
from pathlib import Path

current_dir = Path(__file__).resolve().parent
parent_dir = current_dir.parent
backend_dir = parent_dir / "backend"
for p in [str(backend_dir), str(parent_dir), str(current_dir), os.getcwd()]:
    if p not in sys.path:
        sys.path.insert(0, p)

try:
    from app.main import app
except Exception as e:
    err_msg = traceback.format_exc()
    print("FATAL ERROR IMPORTING APP:\n" + err_msg)
    from fastapi import FastAPI
    from fastapi.responses import PlainTextResponse

    app = FastAPI(title="Fee Auditor - Error Fallback")

    @app.api_route("/{full_path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
    def error_route(full_path: str = ""):
        return PlainTextResponse(f"FastAPI Startup Error:\n\n{err_msg}", status_code=500)
