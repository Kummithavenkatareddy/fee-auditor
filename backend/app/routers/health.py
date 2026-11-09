from fastapi import APIRouter
from app.services.azure_client import test_azure_connection
from app.config import settings

router = APIRouter(prefix="/api/health", tags=["Health"])


@router.get("")
def get_health():
    """System health check and Azure Document Intelligence configuration status."""
    azure_status = test_azure_connection()
    return {
        "status": "online",
        "app_name": "Fee Receipt & Invoice Auditor",
        "azure_configured": azure_status.get("connected", False),
        "azure_details": azure_status,
        "academic_term": {
            "start": settings.ACADEMIC_TERM_START,
            "end": settings.ACADEMIC_TERM_END,
        },
        "confidence_threshold": settings.CONFIDENCE_THRESHOLD,
    }

