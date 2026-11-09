import io
import logging
from typing import Optional
from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import AnalyzeResult
from azure.core.credentials import AzureKeyCredential
from azure.core.exceptions import (
    AzureError,
    ClientAuthenticationError,
    HttpResponseError,
    ResourceNotFoundError,
    ServiceResponseError,
)
from reportlab.pdfgen import canvas
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.config import settings

logger = logging.getLogger(__name__)

_client: Optional[DocumentIntelligenceClient] = None


def get_azure_client() -> DocumentIntelligenceClient:
    """Return a singleton DocumentIntelligenceClient instance with explicit api_version and normalized endpoint."""
    global _client
    if _client is None:
        endpoint = settings.canonical_azure_endpoint
        key = settings.AZURE_DOCUMENT_INTELLIGENCE_KEY.strip()
        api_version = settings.AZURE_API_VERSION or "2024-11-30"

        if not endpoint or not key:
            raise ValueError(
                "Azure Document Intelligence endpoint or key is not configured in environment."
            )

        # Mask endpoint for logging, never log credentials or keys
        masked_endpoint = (
            endpoint.split(".")[0][:12] + "***.cognitiveservices.azure.com"
            if "cognitiveservices.azure.com" in endpoint
            else "configured-endpoint"
        )
        logger.info(
            "Initializing DocumentIntelligenceClient (endpoint: %s, api_version: %s)",
            masked_endpoint,
            api_version,
        )

        try:
            _client = DocumentIntelligenceClient(
                endpoint=endpoint,
                credential=AzureKeyCredential(key),
                api_version=api_version,
            )
        except Exception as exc:
            logger.error("Failed to initialize DocumentIntelligenceClient: %s", type(exc).__name__)
            raise
    return _client


def _generate_minimal_probe_pdf() -> bytes:
    """Generate an in-memory 1-page PDF for live connectivity verification."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    c.setFont("Helvetica", 10)
    c.drawString(100, 750, "Azure Document Intelligence Probe")
    c.drawString(100, 730, "Invoice #: PROBE-001")
    c.drawString(100, 710, "Total: $1.00")
    c.showPage()
    c.save()
    buf.seek(0)
    return buf.getvalue()


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((ServiceResponseError, ConnectionError, ConnectionResetError)),
    reraise=True,
)
def analyze_document_bytes(
    file_bytes: bytes,
    model_id: str = "prebuilt-invoice",
    content_type: str = "application/pdf",
) -> AnalyzeResult:
    """Submit document binary to Azure Document Intelligence and wait for polled AnalyzeResult.

    Retries transient connection resets and network timeouts.
    """
    client = get_azure_client()
    logger.info("Submitting document to Azure (model: %s, size: %d bytes)", model_id, len(file_bytes))
    try:
        poller = client.begin_analyze_document(
            model_id=model_id,
            body=file_bytes,
            content_type=content_type,
        )
        result: AnalyzeResult = poller.result()
        logger.info(
            "Azure analysis succeeded (model: %s, doc_count: %d)",
            model_id,
            len(result.documents) if result.documents else 0,
        )
        return result
    except ClientAuthenticationError as cae:
        logger.error("Azure Authentication Error: Invalid credentials or unauthorized access.")
        raise
    except ResourceNotFoundError as rnfe:
        logger.error("Azure Resource Not Found: Model '%s' or endpoint unavailable.", model_id)
        raise
    except HttpResponseError as hre:
        logger.error("Azure HTTP Response Error (status %s): %s", hre.status_code, str(hre.message)[:200])
        raise
    except AzureError as ae:
        logger.error("Azure Service Error: %s", str(ae)[:200])
        raise
    except Exception as exc:
        logger.error("Unexpected error during Azure analysis: %s", type(exc).__name__)
        raise


def test_azure_connection(perform_live_probe: bool = False) -> dict:
    """Verify Azure Document Intelligence configuration and optionally execute a live probe."""
    endpoint = settings.AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT
    key = settings.AZURE_DOCUMENT_INTELLIGENCE_KEY
    api_version = settings.AZURE_API_VERSION or "2024-11-30"

    if not endpoint or not key:
        return {
            "status": "error",
            "connected": False,
            "message": "Missing AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT or AZURE_DOCUMENT_INTELLIGENCE_KEY",
        }

    try:
        client = get_azure_client()

        if perform_live_probe:
            probe_bytes = _generate_minimal_probe_pdf()
            res = analyze_document_bytes(
                file_bytes=probe_bytes,
                model_id="prebuilt-invoice",
                content_type="application/pdf",
            )
            return {
                "status": "ok",
                "connected": True,
                "live_probe": "succeeded",
                "api_version": api_version,
                "model_tested": "prebuilt-invoice",
                "message": "Live Azure Document Intelligence request completed successfully.",
            }

        return {
            "status": "ok",
            "connected": True,
            "api_version": api_version,
            "message": "Azure Document Intelligence client successfully configured.",
        }
    except ClientAuthenticationError:
        return {
            "status": "error",
            "connected": False,
            "message": "Authentication failed: Azure key rejected.",
        }
    except Exception as exc:
        return {
            "status": "error",
            "connected": False,
            "message": f"Connection check failed: {type(exc).__name__}",
        }
