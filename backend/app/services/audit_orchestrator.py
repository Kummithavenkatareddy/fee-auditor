import logging
import uuid
from datetime import datetime, timezone
from typing import List, Optional, Dict, Tuple, Any

from app.schemas.document import DocumentExtraction, BatchUploadResponse
from app.services.extractor import extract_document
from app.services.validator import apply_all_validation_rules
from app.services.storage import storage_service
from app.db.repository import (
    save_document,
    get_document_by_id,
    get_existing_hashes_with_filenames,
    get_existing_business_keys,
    get_existing_receipt_keys,
    normalize_business_key,
    normalize_receipt_key,
)

logger = logging.getLogger(__name__)


class AuditOrchestrator:
    """Central audit orchestration service executing the strict sequential pipeline:

    Document Upload -> Persistent Storage -> Azure Extraction -> Normalization
    -> Deterministic Validation -> Audit Status Calculation -> SQLite Persistence -> Results API.
    """

    def __init__(self):
        pass

    def process_document(
        self,
        file_bytes: bytes,
        filename: str,
        preferred_model: Optional[str] = None,
        batch_id: Optional[str] = None,
        running_hashes: Optional[Dict[str, str]] = None,
        running_business_keys: Optional[Dict[Tuple[str, str], str]] = None,
        running_receipt_keys: Optional[Dict[Tuple[str, str, str], str]] = None,
        owner_user_id: Optional[str] = "system_default",
    ) -> DocumentExtraction:
        """Execute persistent storage, extraction, deterministic validation, and persistence for a single document."""
        user_id = owner_user_id or "system_default"

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
        b_keys_map = running_business_keys if running_business_keys is not None else get_existing_business_keys(owner_user_id=user_id)
        r_keys_map = running_receipt_keys if running_receipt_keys is not None else get_existing_receipt_keys(owner_user_id=user_id)

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

        # 7. Update running lookup sets
        if running_hashes is not None and not validated_doc.is_exact_duplicate:
            running_hashes[validated_doc.file_hash] = validated_doc.file_name

        b_key = normalize_business_key(validated_doc.vendor_name.value, validated_doc.invoice_id.value)
        if b_key and running_business_keys is not None and not validated_doc.is_duplicate:
            running_business_keys[b_key] = validated_doc.file_name

        if running_receipt_keys is not None and validated_doc.document_type == "receipt":
            r_key = normalize_receipt_key(validated_doc.vendor_name.value, validated_doc.invoice_date.value, validated_doc.total.value)
            if r_key:
                running_receipt_keys[r_key] = validated_doc.file_name

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

        b_keys_map = get_existing_business_keys(owner_user_id=user_id)
        self_b_key = normalize_business_key(doc.vendor_name.value, doc.invoice_id.value)
        if self_b_key:
            b_keys_map.pop(self_b_key, None)

        r_keys_map = get_existing_receipt_keys(owner_user_id=user_id)
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
        return validated_doc

    def process_batch(
        self,
        files_data: List[Tuple[str, bytes]],
        preferred_model: Optional[str] = None,
        owner_user_id: Optional[str] = "system_default",
    ) -> BatchUploadResponse:
        """Process a batch of documents with intra-batch duplicate detection and partial failure isolation."""
        batch_id = str(uuid.uuid4())
        user_id = owner_user_id or "system_default"
        logger.info("AuditOrchestrator: Ingesting batch %s with %d files for user %s", batch_id, len(files_data), user_id)

        running_hashes = get_existing_hashes_with_filenames(owner_user_id=user_id)
        running_business_keys = get_existing_business_keys(owner_user_id=user_id)
        running_receipt_keys = get_existing_receipt_keys(owner_user_id=user_id)

        processed_docs: List[DocumentExtraction] = []
        errors: List[dict] = []

        for filename, content in files_data:
            try:
                if not content:
                    errors.append({"file_name": filename, "error": "Document binary payload is empty."})
                    continue

                doc = self.process_document(
                    file_bytes=content,
                    filename=filename,
                    preferred_model=preferred_model,
                    batch_id=batch_id,
                    running_hashes=running_hashes,
                    running_business_keys=running_business_keys,
                    running_receipt_keys=running_receipt_keys,
                    owner_user_id=user_id,
                )
                processed_docs.append(doc)
            except Exception as exc:
                logger.error("Failed to audit document '%s': %s", filename, str(exc), exc_info=True)
                errors.append({"file_name": filename, "error": f"{type(exc).__name__}: {str(exc)}"})

        return BatchUploadResponse(
            batch_id=batch_id,
            total_files=len(files_data),
            successful_extractions=len(processed_docs),
            failed_extractions=len(errors),
            documents=processed_docs,
            errors=errors,
        )


# Singleton orchestrator instance
orchestrator = AuditOrchestrator()
