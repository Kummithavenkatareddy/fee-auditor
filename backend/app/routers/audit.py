import logging
from typing import List, Optional, Tuple
from pathlib import Path
from pydantic import BaseModel
from fastapi import APIRouter, File, Form, HTTPException, UploadFile, Query, Response, Depends, status

from app.config import settings
from app.schemas.document import (
    BatchUploadResponse,
    DocumentExtraction,
    DashboardSummary,
    ManualReviewUpdate,
)
from app.services.audit_orchestrator import orchestrator
from app.services.export import generate_audit_csv
from app.services.storage import storage_service
from app.db.repository import (
    get_document_by_id,
    get_all_documents,
    update_manual_review,
    get_dashboard_summary,
    delete_all_documents,
    delete_document,
    bulk_delete_documents,
    reset_user_data,
    get_content_safety_events,
)
from app.dependencies.auth import require_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/audit", tags=["Audit"])

ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg"}


class BulkDeleteRequest(BaseModel):
    document_ids: List[str]


@router.post("/upload", response_model=BatchUploadResponse)
async def batch_upload_documents(
    files: List[UploadFile] = File(...),
    preferred_model: Optional[str] = Form(None),
    current_user: dict = Depends(require_current_user),
):
    """Batch and single document upload endpoint supporting PDF, PNG, and JPEG fee receipts and invoices."""
    if not files or len(files) == 0:
        raise HTTPException(status_code=400, detail="No files provided for upload.")

    user_id = current_user["id"]
    files_data: List[Tuple[str, bytes]] = []
    errors: List[dict] = []

    for file in files:
        filename = file.filename or "unknown_file"
        file_ext = "." + filename.split(".")[-1].lower() if "." in filename else ""

        if file_ext not in ALLOWED_EXTENSIONS:
            logger.warning("Unsupported file type '%s' for '%s'", file_ext, filename)
            errors.append(
                {
                    "file_name": filename,
                    "error": f"Unsupported file type '{file_ext}'. Allowed types: PDF, PNG, JPEG.",
                }
            )
            continue

        # 1. Quick rejection if metadata reports file size > limit
        if file.size is not None and file.size > settings.max_upload_size_bytes:
            logger.warning("Rejected oversized file '%s' (size: %d bytes)", filename, file.size)
            errors.append(
                {
                    "file_name": filename,
                    "error": (
                        f"File exceeds maximum allowed upload size of {settings.MAX_UPLOAD_SIZE_MB} MB "
                        f"({file.size / (1024 * 1024):.2f} MB provided)."
                    ),
                }
            )
            continue

        # 2. Chunked stream reading to reject oversized files before buffering payload into memory
        try:
            max_bytes = settings.max_upload_size_bytes
            chunk_size = 1024 * 1024  # 1 MB chunk
            chunks: List[bytes] = []
            total_bytes = 0
            is_oversized = False

            while True:
                chunk = await file.read(chunk_size)
                if not chunk:
                    break
                total_bytes += len(chunk)
                if total_bytes > max_bytes:
                    is_oversized = True
                    break
                chunks.append(chunk)

            if is_oversized:
                logger.warning(
                    "Rejected oversized file '%s' (> %d MB streamed)",
                    filename,
                    settings.MAX_UPLOAD_SIZE_MB,
                )
                errors.append(
                    {
                        "file_name": filename,
                        "error": f"File exceeds maximum allowed upload size of {settings.MAX_UPLOAD_SIZE_MB} MB.",
                    }
                )
                continue

            content = b"".join(chunks)
            if not content:
                errors.append({"file_name": filename, "error": "Uploaded file is empty."})
                continue
            files_data.append((filename, content))
        except Exception as exc:
            errors.append({"file_name": filename, "error": f"Read error: {str(exc)}"})

    # Process through central audit orchestrator
    result = orchestrator.process_batch(
        files_data=files_data,
        preferred_model=preferred_model,
        owner_user_id=user_id,
    )

    # Append any pre-validation file errors
    result.errors.extend(errors)
    result.total_files = len(files)
    result.failed_extractions += len(errors)

    return result


@router.post("/documents/{document_id}/revalidate", response_model=DocumentExtraction)
def revalidate_document_endpoint(
    document_id: str,
    current_user: dict = Depends(require_current_user),
):
    """Re-run deterministic validation rules on an existing document without modifying original extraction."""
    user_id = current_user["id"]
    doc = orchestrator.revalidate_document(document_id, owner_user_id=user_id)
    if not doc:
        raise HTTPException(status_code=404, detail=f"Document '{document_id}' not found.")
    return doc


@router.get("/documents", response_model=List[DocumentExtraction])
def list_documents(
    status: Optional[str] = Query(None, description="Filter by audit_status: clean, flagged, reviewed"),
    current_user: dict = Depends(require_current_user),
):
    """List all extracted documents with optional status filtering, strictly scoped to authenticated user."""
    user_id = current_user["id"]
    return get_all_documents(status_filter=status, owner_user_id=user_id)


@router.get("/documents/{document_id}", response_model=DocumentExtraction)
def get_document(
    document_id: str,
    current_user: dict = Depends(require_current_user),
):
    """Get single document details, line items, and raw Azure JSON, strictly enforcing data isolation."""
    user_id = current_user["id"]
    doc = get_document_by_id(document_id, owner_user_id=user_id)
    if not doc:
        raise HTTPException(status_code=404, detail=f"Document '{document_id}' not found.")
    return doc


@router.get("/documents/{document_id}/file")
def get_document_file(
    document_id: str,
    current_user: dict = Depends(require_current_user),
):
    """Retrieve original file binary for workspace preview and download."""
    user_id = current_user["id"]
    doc = get_document_by_id(document_id, owner_user_id=user_id)
    if not doc:
        raise HTTPException(status_code=404, detail=f"Document '{document_id}' not found.")

    file_bytes = None
    content_type = doc.content_type or "application/pdf"

    if doc.storage_key:
        result = storage_service.get_file(user_id=doc.owner_user_id or user_id, storage_key=doc.storage_key)
        if result:
            file_bytes, content_type = result

    if not file_bytes:
        raise HTTPException(status_code=404, detail="Original document file binary not found in storage.")

    filename = doc.original_filename or doc.file_name or "document.pdf"
    return Response(
        content=file_bytes,
        media_type=content_type,
        headers={
            "Content-Disposition": f"inline; filename=\"{filename}\"",
            "Cache-Control": "private, max-age=3600",
        },
    )


@router.delete("/documents/{document_id}")
def delete_single_document(
    document_id: str,
    current_user: dict = Depends(require_current_user),
):
    """Delete a single document and remove its file from storage."""
    user_id = current_user["id"]
    success = delete_document(document_id, owner_user_id=user_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Document '{document_id}' not found or unauthorized.")
    return {"message": f"Document '{document_id}' deleted successfully."}


@router.post("/documents/bulk-delete")
def bulk_delete_documents_endpoint(
    payload: BulkDeleteRequest,
    current_user: dict = Depends(require_current_user),
):
    """Delete multiple documents and remove their files from storage."""
    user_id = current_user["id"]
    deleted_count = bulk_delete_documents(payload.document_ids, owner_user_id=user_id)
    return {
        "message": f"Successfully deleted {deleted_count} document(s).",
        "deleted_count": deleted_count,
    }


@router.patch("/documents/{document_id}/review")
def review_document(
    document_id: str,
    payload: ManualReviewUpdate,
    current_user: dict = Depends(require_current_user),
):
    """Update manual review status (approved / rejected / pending) and audit notes."""
    user_id = current_user["id"]
    success = update_manual_review(
        doc_id=document_id,
        status=payload.manual_review_status,
        notes=payload.notes,
        owner_user_id=user_id,
    )
    if not success:
        raise HTTPException(status_code=404, detail=f"Document '{document_id}' not found or unauthorized.")
    return {"message": "Manual review status updated successfully.", "status": payload.manual_review_status}


@router.get("/summary", response_model=DashboardSummary)
def get_summary(current_user: dict = Depends(require_current_user)):
    """Get dashboard summary metrics, strictly scoped to authenticated user."""
    user_id = current_user["id"]
    return get_dashboard_summary(owner_user_id=user_id)


@router.get("/export/csv")
def export_csv(current_user: dict = Depends(require_current_user)):
    """Download full audit results as a CSV file generated via Pandas, strictly scoped to user."""
    user_id = current_user["id"]
    docs = get_all_documents(owner_user_id=user_id)
    csv_bytes = generate_audit_csv(documents=docs)
    return Response(
        content=csv_bytes,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=fee_audit_results.csv"},
    )


@router.delete("/reset")
def reset_database(current_user: dict = Depends(require_current_user)):
    """Reset the database for clean testing."""
    user_id = current_user["id"]
    if user_id and user_id != "system_default":
        reset_user_data(user_id)
    else:
        delete_all_documents()
    return {"message": "Database reset completed successfully."}


@router.get("/content-safety-events")
def list_content_safety_events(current_user: dict = Depends(require_current_user)):
    """Retrieve Content Safety screening and rejection events for the current user."""
    user_id = current_user["id"]
    return get_content_safety_events(owner_user_id=user_id)

