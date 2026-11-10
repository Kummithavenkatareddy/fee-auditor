import sys
import traceback
from pathlib import Path

# Add backend directory and parent directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
parent_dir = backend_dir.parent
for path in [str(backend_dir), str(parent_dir)]:
    if path not in sys.path:
        sys.path.insert(0, path)

try:
    from app.main import app
except Exception as e:
    startup_traceback = traceback.format_exc()
    print("FATAL SERVERLESS STARTUP ERROR:\n" + startup_traceback)
    from fastapi import FastAPI, Response

    app = FastAPI(title="Fee Auditor - Startup Error")

    @app.api_route("/{full_path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
    async def startup_error_handler(full_path: str = ""):
        return Response(
            content=f"Fee Auditor Serverless Startup Crash:\n\n{startup_traceback}",
            status_code=500,
            media_type="text/plain",
        )

# Expose both app and handler for Vercel runtime detection
handler = app
