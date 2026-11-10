import sys
import os
import logging
from pathlib import Path
from contextlib import asynccontextmanager

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.db.session import init_db
from app.routers import health, audit, auth, users

logger = logging.getLogger("fee_auditor")


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        init_db()
    except Exception as e:
        logger.warning(f"Database initialization during lifespan: {e}")
    yield


app = FastAPI(
    title="Fee Receipt & Invoice Auditor API",
    description="Azure AI Document Intelligence powered auditor for fee receipts and invoices.",
    version="1.0.0",
    lifespan=lifespan,
)

# Strict production CORS matching deployed frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_origin_regex=r"https:\/\/fee-auditor-frontend.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition", "Authorization"],
)

app.include_router(health.router)
app.include_router(audit.router)
app.include_router(auth.router, prefix="/api")
app.include_router(users.router, prefix="/api")


@app.get("/")
def root():
    return {
        "message": "Fee Receipt & Invoice Auditor API is running.",
        "docs_url": "/docs",
        "health_url": "/api/health",
        "status": "online",
    }
