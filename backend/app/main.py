import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.db.session import init_db
from app.routers import health, audit, auth, users

# Setup structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("fee_auditor")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown events."""
    logger.info("Initializing SQLite database tables and indexes...")
    try:
        init_db()
        logger.info("Fee Receipt & Invoice Auditor backend started successfully.")
    except Exception as e:
        logger.warning(f"Database initialization during lifespan encountered non-fatal error: {e}")
    yield
    logger.info("Fee Receipt & Invoice Auditor backend shutting down.")


app = FastAPI(
    title="Fee Receipt & Invoice Auditor API",
    description="Azure AI Document Intelligence powered auditor for fee receipts and invoices.",
    version="1.0.0",
    lifespan=lifespan,
)

# Enable CORS for configured frontend origins (wildcards disallowed with credentials)
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
    }

