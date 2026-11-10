import logging
import uuid
import hashlib
import threading
from datetime import datetime, timezone
from typing import List, Optional, Dict, Tuple, Any

from app.schemas.document import (
    DocumentExtraction,
    BatchUploadResponse,
    DuplicateResponse,
    ContentSafetyResult,
    ContentScreeningRejection,
)
from app.services.extractor import extract_document
from app.services.validator import apply_all_validation_rules
from app.services.storage import storage_service
from app.services.content_safety import content_safety_service
from app.utils.extraction_report_formatter import format_extraction_report
from app.db.repository import (
    save_document,
    get_document_by_id,
    get_document_by_hash,
    get_existing_hashes_with_filenames,
    get_existing_business_keys_with_docs,
    get_existing_receipt_keys_with_docs,
    normalize_business_key,
    normalize_receipt_key,
    save_content_safety_event,
)

logger = logging.getLogger(__name__)


class AuditOrchestrator:
    """Central audit orchestration service executing the strict sequential pipeline:

    Document Upload -> Persistent Storage -> Azure Extraction -> Normalization
    -> Deterministic Validation -> Audit Status Calculation -> SQLite Persistence -> Results API.
    """

    def __init__(self):
        self._lock = threading.Lock()

    def process_document(
        self,
        file_bytes: bytes,
        filename: str,
        preferred_model: Optional[str] = None,
        batch_id: Optional[str] = None,
        running_hashes: Optional[Dict[str, str]] = None,
        running_business_keys: Optional[Dict[Tuple[str, str], Dict[str, Any]]] = None,
        running_receipt_keys: Optional[Dict[Tuple[str, str, str], Dict[str, Any]]] = None,
        owner_user_id: Optional[str] = "system_default",
        content_safety_result: Optional[ContentSafetyResult] = None,
    ) -> DocumentExtraction:
        """Execute persistent storage, extraction, deterministic validation, and persistence for a single document."""
        user_id = owner_user_id or "system_default"

        # Pre-Screening: Azure AI Content Safety
        # If not already screened prior to calling process_document, screen now.
        if content_safety_result is None:
            content_safety_result = content_safety_service.screen_document(
                file_bytes=file_bytes,
                filename=filename,
            )
            if not content_safety_result.is_safe:
                sha256_hash = hashlib.sha256(file_bytes).hexdigest()
                detected_cat = None
                for c in content_safety_result.categories:
                    if c.flagged:
                        detected_cat = c.category
                        break
                save_content_safety_event(
                    file_name=filename,
                    sha256_hash=sha256_hash,
                    status=content_safety_result.status,
                    rejection_reason=content_safety_result.rejection_reason or "Rejected by Content Safety",
                    owner_user_id=user_id,
                    detected_category=detected_cat,
                    severity=content_safety_result.highest_severity,
                    action_taken=content_safety_result.action_taken,
                    details=content_safety_result.model_dump(),
                )
                raise ValueError(
                    f"Document rejected by Content Safety: {content_safety_result.rejection_reason}"
                )

        # 1. Save document file into persistent storage library
        storage_key, sha256_hash, file_size, content_type = storage_service.save_file(
            user_id=user_id,
            filename=filename,
            content=file_bytes,
        )

        # 2. Azure Extraction & Normalization
        extraction = extract_document(
            file_bytes=file_bytes,
            filename=filename,
            preferred_model=preferred_model,
        )

        # Attach Content Safety metadata
        extraction.content_safety = content_safety_result
        extraction.content_safety_status = content_safety_result.status

        # Attach persistent library metadata
        extraction.storage_key = storage_key
        extraction.original_filename = filename
        extraction.content_type = content_type
        extraction.file_size = file_size
        extraction.sha256_hash = sha256_hash
        extraction.owner_user_id = user_id
        extraction.uploaded_at = datetime.now(timezone.utc).isoformat()
        extraction.processing_status = "completed"

        # 3. Lookup existing records for duplicate detection (cross-batch & intra-batch) scoped to user
        hashes_map = running_hashes if running_hashes is not None else get_existing_hashes_with_filenames(owner_user_id=user_id)
        b_keys_map = running_business_keys if running_business_keys is not None else get_existing_business_keys_with_docs(owner_user_id=user_id)
        r_keys_map = running_receipt_keys if running_receipt_keys is not None else get_existing_receipt_keys_with_docs(owner_user_id=user_id)

        # 4. Deterministic Validation Engine (V01-V05)
        validated_doc = apply_all_validation_rules(
            doc=extraction,
            existing_hashes=hashes_map,
            existing_business_keys=b_keys_map,
            existing_receipt_keys=r_keys_map,
        )

        # 5. Audit Trail Event
        now_iso = datetime.now(timezone.utc).isoformat()
        audit_event = {
            "event": "audit_execution",
            "timestamp": now_iso,
            "rules_applied": ["V01", "V02", "V03", "V04", "V05"],
            "flags_detected": [f.rule_id for f in validated_doc.validation_flags],
            "audit_status": validated_doc.audit_status,
        }
        validated_doc.audit_history.append(audit_event)

        # 6. SQLite Persistence with user isolation
        doc_id = save_document(validated_doc, batch_id=batch_id, owner_user_id=user_id)
        validated_doc.id = doc_id

        # Human-Readable Structured Extraction Report Logging (P09)
        report_text = format_extraction_report(validated_doc, use_colors=False)
        logger.info("\n%s", report_text)

        # Raw Azure JSON preserved in database; logged only at DEBUG level
        if logger.isEnabledFor(logging.DEBUG) and validated_doc.raw_azure_json:
            logger.debug("Raw Azure JSON for '%s':\n%s", validated_doc.file_name, validated_doc.raw_azure_json)

        # 7. Update running lookup sets
        if running_hashes is not None and not validated_doc.is_exact_duplicate:
            running_hashes[validated_doc.file_hash] = validated_doc.file_name

        b_key = normalize_business_key(validated_doc.vendor_name.value, validated_doc.invoice_id.value)
        if b_key and running_business_keys is not None and not validated_doc.is_duplicate:
            running_business_keys[b_key] = {
                "id": validated_doc.id,
                "file_name": validated_doc.file_name,
                "document_type": validated_doc.document_type,
            }

        if running_receipt_keys is not None and validated_doc.document_type == "receipt":
            r_key = normalize_receipt_key(validated_doc.vendor_name.value, validated_doc.invoice_date.value, validated_doc.total.value)
            if r_key:
                running_receipt_keys[r_key] = {
                    "id": validated_doc.id,
                    "file_name": validated_doc.file_name,
                    "document_type": validated_doc.document_type,
                }

        return validated_doc

    def revalidate_document(self, doc_id: str, owner_user_id: Optional[str] = None) -> Optional[DocumentExtraction]:
        """Re-run deterministic validation rules idempotently without overwriting original extraction values."""
        user_id = owner_user_id or "system_default"
        doc = get_document_by_id(doc_id, owner_user_id=owner_user_id)
        if not doc:
            return None

        # Lookup duplicate keys excluding self
        hashes_map = get_existing_hashes_with_filenames(owner_user_id=user_id)
        hashes_map.pop(doc.file_hash, None)

        b_keys_map = get_existing_business_keys_with_docs(owner_user_id=user_id)
        self_b_key = normalize_business_key(doc.vendor_name.value, doc.invoice_id.value)
        if self_b_key:
            b_keys_map.pop(self_b_key, None)

        r_keys_map = get_existing_receipt_keys_with_docs(owner_user_id=user_id)
        self_r_key = normalize_receipt_key(doc.vendor_name.value, doc.invoice_date.value, doc.total.value)
        if self_r_key:
            r_keys_map.pop(self_r_key, None)

        # Re-apply validation rules
        validated_doc = apply_all_validation_rules(
            doc=doc,
            existing_hashes=hashes_map,
            existing_business_keys=b_keys_map,
            existing_receipt_keys=r_keys_map,
        )

        # Record re-validation event
        now_iso = datetime.now(timezone.utc).isoformat()
        reval_event = {
            "event": "revalidation",
            "timestamp": now_iso,
            "flags_count": len(validated_doc.validation_flags),
            "audit_status": validated_doc.audit_status,
        }
        validated_doc.audit_history.append(reval_event)

        # Save idempotently
        save_document(validated_doc, owner_user_id=user_id)

        # Human-Readable Structured Extraction Report Logging on Revalidation (P09)
        report_text = format_extraction_report(validated_doc, use_colors=False)
        logger.info("\n%s", report_text)

        return validated_doc

    def process_batch(
        self,
        files_data: List[Tuple[str, bytes]],
        preferred_model: Optional[str] = None,
        owner_user_id: Optional[str] = "system_default",
    ) -> BatchUploadResponse:
        """Process a batch of documents with Level 1 exact duplicate pre-check,

        intra-batch duplicate detection, and partial failure isolation.
        """
        batch_id = str(uuid.uuid4())
        user_id = owner_user_id or "system_default"
        logger.info("AuditOrchestrator: Ingesting batch %s with %d files for user %s", batch_id, len(files_data), user_id)

        with self._lock:
            running_hashes = get_existing_hashes_with_filenames(owner_user_id=user_id)
            running_business_keys = get_existing_business_keys_with_docs(owner_user_id=user_id)
            running_receipt_keys = get_existing_receipt_keys_with_docs(owner_user_id=user_id)

            # Map of sha256_hash -> document metadata for fast Level 1 exact duplicate detection
            running_hash_meta: Dict[str, Dict[str, Any]] = {}

            processed_docs: List[DocumentExtraction] = []
            duplicates: List[DuplicateResponse] = []
            rejected_docs: List[ContentScreeningRejection] = []
            errors: List[dict] = []
            rejected_by_content_safety_count = 0
            screening_failed_count = 0

            for filename, content in files_data:
                try:
                    if not content:
                        errors.append({"file_name": filename, "error": "Document binary payload is empty."})
                        continue

                    # =========================================================================
                    # LEVEL 1 DUPLICATE DETECTION (Exact Binary Hash Pre-Check)
                    # =========================================================================
                    # Calculate SHA-256 before sending to Azure or creating a document record in SQLite.
                    # Scoped strictly to owner_user_id.
                    sha256_hash = hashlib.sha256(content).hexdigest()

                    existing_meta = running_hash_meta.get(sha256_hash)
                    if not existing_meta:
                        existing_meta = get_document_by_hash(sha256_hash, owner_user_id=user_id)

                    if existing_meta:
                        # Exact file duplicate detected for this user!
                        # Rule: Do NOT create another document record in SQLite.
                        # Rule: Do NOT send the file to Azure again.
                        # Rule: Do NOT create a new extraction.
                        # Rule: Do NOT overwrite or alter original document audit history.
                        existing_id = existing_meta["id"]
                        existing_file = existing_meta.get("original_filename") or existing_meta.get("file_name") or filename
                        doc_type = existing_meta.get("document_type") or "invoice"
                        audit_status = existing_meta.get("audit_status") or "clean"
                        upload_date = existing_meta.get("uploaded_at") or existing_meta.get("created_at") or datetime.now(timezone.utc).isoformat()

                        logger.info(
                            "Exact file duplicate detected for '%s' matching existing document '%s' (ID: %s). Skipping Azure extraction and DB persistence.",
                            filename,
                            existing_file,
                            existing_id,
                        )

                        dup_response = DuplicateResponse(
                            existing_document_id=existing_id,
                            filename=filename,
                            existing_file_name=existing_file,
                            document_type=doc_type,
                            audit_status=audit_status,
                            upload_date=upload_date,
                            is_duplicate=True,
                            is_exact_duplicate=True,
                            duplicate_type="exact",
                            message=(
                                f"Exact duplicate document detected. An identical file matching original "
                                f"document '{existing_file}' (ID: {existing_id}) has already been ingested. "
                                f"Re-processing skipped to preserve original audit record."
                            ),
                            document_url=f"/api/audit/documents/{existing_id}",
                        )
                        duplicates.append(dup_response)
                        continue

                    # =========================================================================
                    # PRE-SCREENING: Azure AI Content Safety
                    # =========================================================================
                    # Screen document content (text and images) before sending to Azure Document Intelligence
                    cs_result = content_safety_service.screen_document(
                        file_bytes=content,
                        filename=filename,
                    )

                    if not cs_result.is_safe:
                        detected_cat = None
                        for c in cs_result.categories:
                            if c.flagged:
                                detected_cat = c.category
                                break
                        if not detected_cat and cs_result.matched_custom_terms:
                            detected_cat = "CustomProhibitedTerm"
                        elif not detected_cat and cs_result.matched_blocklists:
                            detected_cat = "AzureBlocklist"

                        if cs_result.status == "rejected":
                            rejected_by_content_safety_count += 1
                            rej = ContentScreeningRejection(
                                file_name=filename,
                                status="rejected",
                                detected_category=detected_cat,
                                severity=cs_result.highest_severity,
                                reason=cs_result.rejection_reason or "Document rejected by Content Safety.",
                                error_message=None,
                            )
                            rejected_docs.append(rej)
                            save_content_safety_event(
                                file_name=filename,
                                sha256_hash=sha256_hash,
                                status="rejected",
                                rejection_reason=cs_result.rejection_reason or "Rejected by Content Safety",
                                owner_user_id=user_id,
                                detected_category=detected_cat,
                                severity=cs_result.highest_severity,
                                action_taken="rejected",
                                details=cs_result.model_dump(),
                            )
                            logger.warning(
                                "Document '%s' REJECTED by Content Safety: %s (Severity: %d)",
                                filename,
                                cs_result.rejection_reason,
                                cs_result.highest_severity,
                            )
                            continue
                        elif cs_result.status == "failed":
                            screening_failed_count += 1
                            rej = ContentScreeningRejection(
                                file_name=filename,
                                status="failed",
                                detected_category=None,
                                severity=0,
                                reason=cs_result.rejection_reason or "Content Safety screening failed.",
                                error_message=cs_result.details or cs_result.rejection_reason,
                            )
                            rejected_docs.append(rej)
                            save_content_safety_event(
                                file_name=filename,
                                sha256_hash=sha256_hash,
                                status="failed",
                                rejection_reason=cs_result.rejection_reason or "Screening failed",
                                owner_user_id=user_id,
                                action_taken="error",
                                details=cs_result.model_dump(),
                            )
                            logger.error(
                                "Document '%s' Content Safety SCREENING FAILED: %s",
                                filename,
                                cs_result.rejection_reason,
                            )
                            continue

                    # =========================================================================
                    # LEVEL 2 & STANDARD PIPELINE (Document Passed Content Safety)
                    # =========================================================================
                    # New safe file: Call Azure prebuilt model, validate (including Level 2 logical duplicate),
                    # and persist to SQLite with multi-user isolation.
                    doc = self.process_document(
                        file_bytes=content,
                        filename=filename,
                        preferred_model=preferred_model,
                        batch_id=batch_id,
                        running_hashes=running_hashes,
                        running_business_keys=running_business_keys,
                        running_receipt_keys=running_receipt_keys,
                        owner_user_id=user_id,
                        content_safety_result=cs_result,
                    )
                    processed_docs.append(doc)

                    # Register in running_hash_meta for intra-batch duplicate detection
                    doc_hash = doc.sha256_hash or doc.file_hash
                    running_hash_meta[doc_hash] = {
                        "id": doc.id,
                        "file_name": doc.original_filename or doc.file_name,
                        "original_filename": doc.original_filename or doc.file_name,
                        "document_type": doc.document_type,
                        "audit_status": doc.audit_status,
                        "uploaded_at": doc.uploaded_at or doc.created_at,
                    }
                except Exception as exc:
                    logger.error("Failed to audit document '%s': %s", filename, str(exc), exc_info=True)
                    errors.append({"file_name": filename, "error": f"{type(exc).__name__}: {str(exc)}"})

        return BatchUploadResponse(
            batch_id=batch_id,
            total_files=len(files_data),
            successful_extractions=len(processed_docs),
            duplicate_files=len(duplicates),
            rejected_by_content_safety=rejected_by_content_safety_count,
            screening_failed=screening_failed_count,
            failed_extractions=len(errors),
            documents=processed_docs,
            duplicates=duplicates,
            rejected_documents=rejected_docs,
            errors=errors,
        )


# Singleton orchestrator instance
orchestrator = AuditOrchestrator()
