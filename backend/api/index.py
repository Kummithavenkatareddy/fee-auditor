import sys
import traceback
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

try:
    from app.main import app
except Exception as e:
    err_msg = traceback.format_exc()
    print("FATAL ERROR IMPORTING APP:\n" + err_msg)
    from fastapi import FastAPI
    from fastapi.responses import PlainTextResponse

    app = FastAPI(title="Fee Auditor - Error")

    @app.api_route("/{full_path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
    def error_route(full_path: str = ""):
        return PlainTextResponse(f"FastAPI Startup Error:\n\n{err_msg}", status_code=500)
