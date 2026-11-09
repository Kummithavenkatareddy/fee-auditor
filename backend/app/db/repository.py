import json
import uuid
import re
from decimal import Decimal
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Set, Dict, Any, Tuple

from app.db.session import get_db_connection
from app.schemas.common import format_canonical_decimal
from app.schemas.document import (
    DocumentExtraction,
    ExtractedField,
    ExtractedLineItem,
    ValidationFlag,
    DashboardSummary,
)
from app.services.storage import storage_service
from app.services.auth_security import hash_token


def normalize_vendor_name(vendor: Optional[str]) -> Optional[str]:
    """Normalize vendor name for business duplicate comparison while preserving distinct entities."""
    if not vendor or not isinstance(vendor, str):
        return None
    raw = vendor.strip().lower()
    if not raw:
        return None
    # Strip common trailing corporate entity designations at the END of the string only
    cleaned = re.sub(
        r"(?:[\s,]+(?:inc|incorporated|llc|corp|corporation|ltd|limited|co|company|pvt(?:\s*ltd)?)\.?)+$",
        "",
        raw,
        flags=re.IGNORECASE,
    ).strip()
    # Strip remaining non-alphanumeric characters except spaces
    v_norm = re.sub(r"[^\w\s]", "", cleaned)
    v_norm = re.sub(r"\s+", " ", v_norm).strip()
    return v_norm or None


def normalize_invoice_id(invoice_id: Optional[str]) -> Optional[str]:
    """Normalize invoice ID by extracting uppercase alphanumeric characters only."""
    if not invoice_id:
        return None
    i_norm = "".join(c for c in str(invoice_id).strip().upper() if c.isalnum())
    return i_norm or None


def normalize_business_key(vendor: Optional[str], invoice_id: Optional[str]) -> Optional[Tuple[str, str]]:
    """Normalize vendor name and invoice ID for business duplicate comparison."""
    v_norm = normalize_vendor_name(vendor)
    i_norm = normalize_invoice_id(invoice_id)
    if not v_norm or not i_norm:
        return None
    return (v_norm, i_norm)


def normalize_receipt_key(merchant: Optional[str], tx_date: Optional[str], total: Optional[str]) -> Optional[Tuple[str, str, str]]:
    """Normalize merchant, date, and total for receipt duplicate strategy."""
    if not merchant or not tx_date or not total:
        return None
    m_norm = normalize_vendor_name(merchant)
    d_norm = str(tx_date).strip()
    t_norm = format_canonical_decimal(total) or str(total).strip()
    if not m_norm or not d_norm or not t_norm:
        return None
    return (m_norm, d_norm, t_norm)


def get_existing_hashes_with_filenames(owner_user_id: Optional[str] = None) -> Dict[str, str]:
    """Retrieve mapping of SHA-256 hash -> filename to identify original duplicate files, strictly scoped to user."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        if owner_user_id:
            cursor.execute(
                "SELECT file_hash, file_name FROM documents WHERE file_hash IS NOT NULL AND owner_user_id = ?;",
                (owner_user_id,),
            )
        else:
            cursor.execute("SELECT file_hash, file_name FROM documents WHERE file_hash IS NOT NULL;")
        rows = cursor.fetchall()
        return {r["file_hash"]: r["file_name"] for r in rows if r["file_hash"]}


def get_existing_hashes(owner_user_id: Optional[str] = None) -> Set[str]:
    """Retrieve existing SHA-256 hashes, strictly scoped to user."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        if owner_user_id:
            cursor.execute(
                "SELECT file_hash FROM documents WHERE owner_user_id = ?;",
                (owner_user_id,),
            )
        else:
            cursor.execute("SELECT file_hash FROM documents;")
        rows = cursor.fetchall()
        return {r["file_hash"] for r in rows if r["file_hash"]}


def get_existing_business_keys(owner_user_id: Optional[str] = None) -> Dict[Tuple[str, str], str]:
    """Retrieve mapping of (norm_vendor, norm_invoice_id) -> filename for business duplicate detection."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        if owner_user_id:
            cursor.execute(
                "SELECT vendor_name, invoice_id, file_name FROM documents WHERE vendor_name IS NOT NULL AND invoice_id IS NOT NULL AND owner_user_id = ?;",
                (owner_user_id,),
            )
        else:
            cursor.execute("SELECT vendor_name, invoice_id, file_name FROM documents WHERE vendor_name IS NOT NULL AND invoice_id IS NOT NULL;")
        rows = cursor.fetchall()
        mapping: Dict[Tuple[str, str], str] = {}
        for r in rows:
            key = normalize_business_key(r["vendor_name"], r["invoice_id"])
            if key:
                mapping[key] = r["file_name"]
        return mapping


def get_existing_receipt_keys(owner_user_id: Optional[str] = None) -> Dict[Tuple[str, str, str], str]:
    """Retrieve mapping of (norm_merchant, date, total) -> filename for receipt duplicate detection."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        if owner_user_id:
            cursor.execute(
                "SELECT vendor_name, invoice_date, total, file_name FROM documents WHERE document_type = 'receipt' AND owner_user_id = ?;",
                (owner_user_id,),
            )
        else:
            cursor.execute("SELECT vendor_name, invoice_date, total, file_name FROM documents WHERE document_type = 'receipt';")
        rows = cursor.fetchall()
        mapping: Dict[Tuple[str, str, str], str] = {}
        for r in rows:
            key = normalize_receipt_key(r["vendor_name"], r["invoice_date"], r["total"])
            if key:
                mapping[key] = r["file_name"]
        return mapping


def save_document(doc: DocumentExtraction, batch_id: Optional[str] = None, owner_user_id: Optional[str] = None) -> str:
    """Save or update an extracted and validated document into SQLite idempotently."""
    doc_id = doc.id or str(uuid.uuid4())
    doc.id = doc_id

    effective_owner = owner_user_id or doc.owner_user_id or "system_default"
    doc.owner_user_id = effective_owner

    subtotal_str = format_canonical_decimal(doc.subtotal.value)
    tax_str = format_canonical_decimal(doc.tax.value)
    total_str = format_canonical_decimal(doc.total.value)

    if not doc.raw_azure_json:
        doc.raw_azure_json = "{}"

    # Ensure normalized fields are set
    if not doc.normalized_vendor_name and doc.vendor_name.value:
        doc.normalized_vendor_name = normalize_vendor_name(doc.vendor_name.value)
    if not doc.normalized_invoice_id and doc.invoice_id.value:
        doc.normalized_invoice_id = normalize_invoice_id(doc.invoice_id.value)

    # Ensure highest severity is calculated
    if not doc.highest_severity and doc.validation_flags:
        severities = {f.severity for f in doc.validation_flags}
        for s in ("CRITICAL", "HIGH", "MEDIUM", "WARNING"):
            if s in severities:
                doc.highest_severity = s
                break

    # Serialize normalized json
    doc.normalized_json = json.dumps(
        doc.model_dump(exclude={"raw_azure_json", "normalized_json"}),
        default=str,
    )

    history_json = json.dumps(doc.audit_history, default=str)

    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Check if document already exists
        cursor.execute("SELECT id, manual_review_status, manual_review_notes FROM documents WHERE id = ?;", (doc_id,))
        existing = cursor.fetchone()

        if existing:
            # Preserve existing manual review status and reviewer notes!
            preserved_review_status = existing["manual_review_status"] or doc.manual_review_status or "pending"
            preserved_review_notes = existing["manual_review_notes"] or doc.manual_review_notes
            effective_audit_status = "reviewed" if preserved_review_status in ("approved", "rejected") else doc.audit_status

            cursor.execute(
                """
                UPDATE documents
                SET audit_status = ?,
                    is_duplicate = ?,
                    is_exact_duplicate = ?,
                    is_business_duplicate = ?,
                    manual_review_status = ?,
                    manual_review_notes = ?,
                    audit_history = ?,
                    normalized_vendor_name = ?,
                    normalized_invoice_id = ?,
                    highest_severity = ?,
                    normalized_json = ?,
                    owner_user_id = ?,
                    original_filename = ?,
                    storage_key = ?,
                    content_type = ?,
                    file_size = ?,
                    sha256_hash = ?,
                    uploaded_at = ?,
                    processing_status = ?
                WHERE id = ?;
                """,
                (
                    effective_audit_status,
                    1 if doc.is_duplicate else 0,
                    1 if doc.is_exact_duplicate else 0,
                    1 if doc.is_business_duplicate else 0,
                    preserved_review_status,
                    preserved_review_notes,
                    history_json,
                    doc.normalized_vendor_name,
                    doc.normalized_invoice_id,
                    doc.highest_severity,
                    doc.normalized_json,
                    effective_owner,
                    doc.original_filename or doc.file_name,
                    doc.storage_key,
                    doc.content_type,
                    doc.file_size,
                    doc.sha256_hash or doc.file_hash,
                    doc.uploaded_at or doc.created_at,
                    doc.processing_status or "completed",
                    doc_id,
                ),
            )
        else:
            # Insert new record
            cursor.execute(
                """
                INSERT INTO documents (
                    id, file_name, file_hash, model_used, document_type, extraction_status,
                    vendor_name, vendor_name_conf,
                    invoice_id, invoice_id_conf,
                    invoice_date, invoice_date_conf,
                    vendor_tax_id, vendor_tax_id_conf,
                    subtotal, subtotal_conf,
                    tax, tax_conf,
                    total, total_conf,
                    is_duplicate, is_exact_duplicate, is_business_duplicate,
                    audit_status, manual_review_status, manual_review_notes,
                    batch_id, created_at, audit_history,
                    normalized_vendor_name, normalized_invoice_id, highest_severity,
                    raw_azure_json, normalized_json,
                    owner_user_id, original_filename, storage_key, content_type,
                    file_size, sha256_hash, uploaded_at, processing_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    doc_id,
                    doc.file_name,
                    doc.file_hash,
                    doc.model_used,
                    doc.document_type,
                    doc.extraction_status,
                    str(doc.vendor_name.value) if doc.vendor_name.value is not None else None,
                    doc.vendor_name.confidence,
                    str(doc.invoice_id.value) if doc.invoice_id.value is not None else None,
                    doc.invoice_id.confidence,
                    str(doc.invoice_date.value) if doc.invoice_date.value is not None else None,
                    doc.invoice_date.confidence,
                    str(doc.vendor_tax_id.value) if doc.vendor_tax_id.value is not None else None,
                    doc.vendor_tax_id.confidence,
                    subtotal_str,
                    doc.subtotal.confidence,
                    tax_str,
                    doc.tax.confidence,
                    total_str,
                    doc.total.confidence,
                    1 if doc.is_duplicate else 0,
                    1 if doc.is_exact_duplicate else 0,
                    1 if doc.is_business_duplicate else 0,
                    doc.audit_status,
                    doc.manual_review_status or "pending",
                    doc.manual_review_notes,
                    batch_id,
                    doc.created_at,
                    history_json,
                    doc.normalized_vendor_name,
                    doc.normalized_invoice_id,
                    doc.highest_severity,
                    doc.raw_azure_json,
                    doc.normalized_json,
                    effective_owner,
                    doc.original_filename or doc.file_name,
                    doc.storage_key,
                    doc.content_type,
                    doc.file_size,
                    doc.sha256_hash or doc.file_hash,
                    doc.uploaded_at or doc.created_at,
                    doc.processing_status or "completed",
                ),
            )

        # 1. Update/insert into extractions table (Phase 2 canonical entity)
        cursor.execute("DELETE FROM extractions WHERE document_id = ?;", (doc_id,))
        fields_dump = {
            "vendor_name": doc.vendor_name.model_dump(),
            "invoice_id": doc.invoice_id.model_dump(),
            "invoice_date": doc.invoice_date.model_dump(),
            "vendor_tax_id": doc.vendor_tax_id.model_dump(),
            "subtotal": doc.subtotal.model_dump(),
            "tax": doc.tax.model_dump(),
            "total": doc.total.model_dump(),
        }
        conf_dump = {
            "vendor_name": doc.vendor_name.confidence,
            "invoice_id": doc.invoice_id.confidence,
            "invoice_date": doc.invoice_date.confidence,
            "vendor_tax_id": doc.vendor_tax_id.confidence,
            "subtotal": doc.subtotal.confidence,
            "tax": doc.tax.confidence,
            "total": doc.total.confidence,
        }
        cursor.execute(
            """
            INSERT INTO extractions (id, document_id, extracted_fields, confidence_data, raw_azure_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?);
            """,
            (
                str(uuid.uuid4()),
                doc_id,
                json.dumps(fields_dump, default=str),
                json.dumps(conf_dump),
                doc.raw_azure_json or "{}",
                doc.created_at or datetime.now(timezone.utc).isoformat(),
            ),
        )

        # 2. Update/insert into audit_runs table (Phase 2 canonical entity)
        cursor.execute("DELETE FROM validation_flags WHERE document_id = ?;", (doc_id,))
        cursor.execute("DELETE FROM audit_runs WHERE document_id = ?;", (doc_id,))
        audit_run_id = str(uuid.uuid4())
        cursor.execute(
            """
            INSERT INTO audit_runs (id, document_id, academic_term_start, academic_term_end, rule_version, audit_status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?);
            """,
            (
                audit_run_id,
                doc_id,
                "2026-08-01",
                "2026-12-31",
                "V01-V05-v1.0",
                doc.audit_status,
                doc.created_at or datetime.now(timezone.utc).isoformat(),
            ),
        )

        # 3. Insert line items
        cursor.execute("DELETE FROM line_items WHERE document_id = ?;", (doc_id,))
        for idx, item in enumerate(doc.line_items):
            cursor.execute(
                """
                INSERT INTO line_items (document_id, item_index, description, quantity, unit_price, amount, confidence)
                VALUES (?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    doc_id,
                    idx,
                    item.description,
                    format_canonical_decimal(item.quantity) or (str(item.quantity) if item.quantity else None),
                    format_canonical_decimal(item.unit_price),
                    format_canonical_decimal(item.amount),
                    item.confidence,
                ),
            )

        # 4. Insert fresh validation flags (both canonical validation_flags and legacy audit_flags)
        cursor.execute("DELETE FROM audit_flags WHERE document_id = ?;", (doc_id,))
        for flag in doc.validation_flags:
            cursor.execute(
                """
                INSERT INTO validation_flags (audit_run_id, document_id, rule_id, severity, target_field, reason, expected_value, actual_value, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    audit_run_id,
                    doc_id,
                    flag.rule_id,
                    flag.severity,
                    flag.field_name,
                    flag.reason,
                    flag.expected_value,
                    flag.actual_value,
                    flag.timestamp or datetime.now(timezone.utc).isoformat(),
                ),
            )
            cursor.execute(
                """
                INSERT INTO audit_flags (document_id, rule_id, rule_name, severity, field_name, reason, expected_value, actual_value, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    doc_id,
                    flag.rule_id,
                    flag.rule_name,
                    flag.severity,
                    flag.field_name,
                    flag.reason,
                    flag.expected_value,
                    flag.actual_value,
                    flag.timestamp or datetime.now(timezone.utc).isoformat(),
                ),
            )

    return doc_id


def get_document_by_id(doc_id: str, owner_user_id: Optional[str] = None) -> Optional[DocumentExtraction]:
    """Retrieve full document extraction with line items, audit flags, raw JSON, with strict multi-user isolation check."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM documents WHERE id = ?;", (doc_id,))
        doc_row = cursor.fetchone()
        if not doc_row:
            return None

        # Check multi-user data isolation strictly: no system_default bleed into authenticated user
        row_keys = set(doc_row.keys())
        doc_owner = doc_row["owner_user_id"] if "owner_user_id" in row_keys else None
        if owner_user_id and doc_owner != owner_user_id:
            return None

        # Fetch line items ordered by item_index
        cursor.execute("SELECT * FROM line_items WHERE document_id = ? ORDER BY item_index ASC, id ASC;", (doc_id,))
        item_rows = cursor.fetchall()
        line_items = [
            ExtractedLineItem(
                item_index=r["item_index"],
                description=r["description"],
                quantity=r["quantity"],
                unit_price=r["unit_price"],
                amount=r["amount"],
                confidence=r["confidence"],
            )
            for r in item_rows
        ]

        # Fetch audit flags
        cursor.execute("SELECT * FROM audit_flags WHERE document_id = ? ORDER BY id ASC;", (doc_id,))
        flag_rows = cursor.fetchall()
        flags = [
            ValidationFlag(
                rule_id=r["rule_id"],
                rule_name=r["rule_name"],
                severity=r["severity"],
                field_name=r["field_name"],
                reason=r["reason"],
                expected_value=r["expected_value"],
                actual_value=r["actual_value"],
                timestamp=r["created_at"],
            )
            for r in flag_rows
        ]

        # Parse audit history
        history = []
        if doc_row["audit_history"]:
            try:
                history = json.loads(doc_row["audit_history"])
            except Exception:
                history = []

        return DocumentExtraction(
            id=doc_row["id"],
            file_name=doc_row["file_name"],
            file_hash=doc_row["file_hash"],
            model_used=doc_row["model_used"],
            document_type=doc_row["document_type"],
            extraction_status=doc_row["extraction_status"] or "succeeded",
            vendor_name=ExtractedField(
                value=doc_row["vendor_name"],
                confidence=doc_row["vendor_name_conf"],
            ),
            invoice_id=ExtractedField(
                value=doc_row["invoice_id"],
                confidence=doc_row["invoice_id_conf"],
            ),
            invoice_date=ExtractedField(
                value=doc_row["invoice_date"],
                confidence=doc_row["invoice_date_conf"],
            ),
            vendor_tax_id=ExtractedField(
                value=doc_row["vendor_tax_id"],
                confidence=doc_row["vendor_tax_id_conf"],
            ),
            subtotal=ExtractedField(
                value=doc_row["subtotal"],
                confidence=doc_row["subtotal_conf"],
            ),
            tax=ExtractedField(
                value=doc_row["tax"],
                confidence=doc_row["tax_conf"],
            ),
            total=ExtractedField(
                value=doc_row["total"],
                confidence=doc_row["total_conf"],
            ),
            line_items=line_items,
            validation_flags=flags,
            is_duplicate=bool(doc_row["is_duplicate"]),
            is_exact_duplicate=bool(doc_row["is_exact_duplicate"]),
            is_business_duplicate=bool(doc_row["is_business_duplicate"]),
            normalized_vendor_name=doc_row["normalized_vendor_name"] if "normalized_vendor_name" in row_keys and doc_row["normalized_vendor_name"] else normalize_vendor_name(doc_row["vendor_name"]),
            normalized_invoice_id=doc_row["normalized_invoice_id"] if "normalized_invoice_id" in row_keys and doc_row["normalized_invoice_id"] else normalize_invoice_id(doc_row["invoice_id"]),
            highest_severity=doc_row["highest_severity"] if "highest_severity" in row_keys else None,
            audit_status=doc_row["audit_status"],
            manual_review_status=doc_row["manual_review_status"],
            manual_review_notes=doc_row["manual_review_notes"],
            created_at=doc_row["created_at"],
            audit_history=history,
            raw_azure_json=doc_row["raw_azure_json"],
            normalized_json=doc_row["normalized_json"],
            owner_user_id=doc_owner or "system_default",
            original_filename=doc_row["original_filename"] if "original_filename" in row_keys else doc_row["file_name"],
            storage_key=doc_row["storage_key"] if "storage_key" in row_keys else None,
            content_type=doc_row["content_type"] if "content_type" in row_keys else None,
            file_size=doc_row["file_size"] if "file_size" in row_keys else None,
            sha256_hash=doc_row["sha256_hash"] if "sha256_hash" in row_keys else doc_row["file_hash"],
            uploaded_at=doc_row["uploaded_at"] if "uploaded_at" in row_keys else doc_row["created_at"],
            processing_status=doc_row["processing_status"] if "processing_status" in row_keys else "completed",
        )


def get_all_documents(status_filter: Optional[str] = None, owner_user_id: Optional[str] = None) -> List[DocumentExtraction]:
    """Retrieve all documents with their line items and validation flags, strictly filtered by user."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        query = "SELECT id FROM documents"
        conditions = []
        params: List[Any] = []

        if owner_user_id:
            conditions.append("owner_user_id = ?")
            params.append(owner_user_id)

        if status_filter:
            conditions.append("audit_status = ?")
            params.append(status_filter)

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY created_at DESC;"

        cursor.execute(query, params)
        rows = cursor.fetchall()
        results: List[DocumentExtraction] = []
        for r in rows:
            doc = get_document_by_id(r["id"], owner_user_id=owner_user_id)
            if doc:
                results.append(doc)
        return results


def update_manual_review(doc_id: str, status: str, notes: Optional[str] = None, owner_user_id: Optional[str] = None) -> bool:
    """Update manual review status (approved/rejected/pending) and notes, recording in review_actions."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        audit_status = "reviewed" if status in ("approved", "rejected") else "flagged"

        # Record event in audit_history
        cursor.execute("SELECT audit_history, owner_user_id FROM documents WHERE id = ?;", (doc_id,))
        row = cursor.fetchone()
        if not row:
            return False

        row_owner = row["owner_user_id"] if "owner_user_id" in row.keys() else None
        if owner_user_id and row_owner != owner_user_id:
            return False

        try:
            history = json.loads(row["audit_history"]) if row["audit_history"] else []
        except Exception:
            history = []

        now_iso = datetime.now(timezone.utc).isoformat()
        history.append({
            "event": "manual_review_update",
            "timestamp": now_iso,
            "new_status": status,
            "notes": notes,
        })

        # Insert into review_actions table (Phase 2 canonical entity)
        action_id = str(uuid.uuid4())
        reviewer_id = owner_user_id or row_owner or "system_default"
        cursor.execute(
            """
            INSERT INTO review_actions (id, document_id, reviewer_user_id, decision, justification, created_at)
            VALUES (?, ?, ?, ?, ?, ?);
            """,
            (action_id, doc_id, reviewer_id, status, notes or "", now_iso),
        )

        cursor.execute(
            """
            UPDATE documents
            SET manual_review_status = ?, manual_review_notes = ?, audit_status = ?, audit_history = ?
            WHERE id = ?;
            """,
            (status, notes, audit_status, json.dumps(history), doc_id),
        )
        return cursor.rowcount > 0


def delete_document(doc_id: str, owner_user_id: Optional[str] = None) -> bool:
    """Delete a single document, its line items, flags, review actions, and physical file from storage."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT storage_key, owner_user_id FROM documents WHERE id = ?;", (doc_id,))
        row = cursor.fetchone()
        if not row:
            return False

        row_owner = row["owner_user_id"] if "owner_user_id" in row.keys() else None
        if owner_user_id and row_owner != owner_user_id:
            return False

        storage_key = row["storage_key"]
        effective_owner = row_owner or owner_user_id or "system_default"

        cursor.execute("DELETE FROM review_actions WHERE document_id = ?;", (doc_id,))
        cursor.execute("DELETE FROM validation_flags WHERE document_id = ?;", (doc_id,))
        cursor.execute("DELETE FROM audit_runs WHERE document_id = ?;", (doc_id,))
        cursor.execute("DELETE FROM extractions WHERE document_id = ?;", (doc_id,))
        cursor.execute("DELETE FROM audit_flags WHERE document_id = ?;", (doc_id,))
        cursor.execute("DELETE FROM line_items WHERE document_id = ?;", (doc_id,))
        cursor.execute("DELETE FROM documents WHERE id = ?;", (doc_id,))

        if storage_key:
            storage_service.delete_file(effective_owner, storage_key)

        return True


def bulk_delete_documents(doc_ids: List[str], owner_user_id: Optional[str] = None) -> int:
    """Delete multiple documents belonging to the user."""
    deleted_count = 0
    for did in doc_ids:
        if delete_document(did, owner_user_id=owner_user_id):
            deleted_count += 1
    return deleted_count


def reset_user_data(owner_user_id: str) -> int:
    """Delete all documents, flags, line items, extractions, runs, review actions, and files for a specific user."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, storage_key FROM documents WHERE owner_user_id = ?;", (owner_user_id,))
        rows = cursor.fetchall()
        count = len(rows)
        for r in rows:
            did = r["id"]
            cursor.execute("DELETE FROM review_actions WHERE document_id = ?;", (did,))
            cursor.execute("DELETE FROM validation_flags WHERE document_id = ?;", (did,))
            cursor.execute("DELETE FROM audit_runs WHERE document_id = ?;", (did,))
            cursor.execute("DELETE FROM extractions WHERE document_id = ?;", (did,))
            cursor.execute("DELETE FROM audit_flags WHERE document_id = ?;", (did,))
            cursor.execute("DELETE FROM line_items WHERE document_id = ?;", (did,))
        cursor.execute("DELETE FROM documents WHERE owner_user_id = ?;", (owner_user_id,))

    storage_service.delete_user_files(owner_user_id)
    return count


def get_dashboard_summary(owner_user_id: Optional[str] = None) -> DashboardSummary:
    """Aggregate dashboard metrics using Decimal precision, strictly scoped to user."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        owner_filter = " WHERE owner_user_id = ?" if owner_user_id else ""
        owner_params = (owner_user_id,) if owner_user_id else ()

        cursor.execute(f"SELECT COUNT(*) AS total FROM documents{owner_filter};", owner_params)
        total_docs = cursor.fetchone()["total"] or 0

        # Decimal calculation for total audited amount
        total_val_dec = Decimal("0.00")
        where_clause = "WHERE total IS NOT NULL"
        if owner_user_id:
            where_clause += " AND owner_user_id = ?"
        cursor.execute(f"SELECT total FROM documents {where_clause};", owner_params)
        for r in cursor.fetchall():
            canonical = format_canonical_decimal(r["total"])
            if canonical:
                total_val_dec += Decimal(canonical)

        clean_where = "WHERE audit_status = 'clean'"
        if owner_user_id:
            clean_where += " AND owner_user_id = ?"
        cursor.execute(f"SELECT COUNT(*) AS cnt FROM documents {clean_where};", owner_params)
        clean_docs = cursor.fetchone()["cnt"] or 0

        flag_where = "WHERE audit_status = 'flagged'"
        if owner_user_id:
            flag_where += " AND owner_user_id = ?"
        cursor.execute(f"SELECT COUNT(*) AS cnt FROM documents {flag_where};", owner_params)
        flagged_docs = cursor.fetchone()["cnt"] or 0

        dup_where = "WHERE is_duplicate = 1"
        if owner_user_id:
            dup_where += " AND owner_user_id = ?"
        cursor.execute(f"SELECT COUNT(*) AS cnt FROM documents {dup_where};", owner_params)
        dup_docs = cursor.fetchone()["cnt"] or 0

        # Pending review documents: clean documents strictly excluded!
        # Document is pending review if audit_status != 'clean' and (audit_status = 'flagged' or manual_review_status = 'pending')
        pending_where = "WHERE audit_status != 'clean' AND (audit_status = 'flagged' OR manual_review_status = 'pending')"
        if owner_user_id:
            pending_where += " AND owner_user_id = ?"
        cursor.execute(f"SELECT COUNT(*) AS cnt FROM documents {pending_where};", owner_params)
        pending_review_docs = cursor.fetchone()["cnt"] or 0

        # Count rule violations across documents for this user
        def count_rule(rule_id: str) -> int:
            if owner_user_id:
                cursor.execute(
                    """
                    SELECT COUNT(DISTINCT f.document_id) AS cnt
                    FROM audit_flags f
                    JOIN documents d ON f.document_id = d.id
                    WHERE f.rule_id = ? AND d.owner_user_id = ?;
                    """,
                    (rule_id, owner_user_id),
                )
            else:
                cursor.execute("SELECT COUNT(DISTINCT document_id) AS cnt FROM audit_flags WHERE rule_id = ?;", (rule_id,))
            return cursor.fetchone()["cnt"] or 0

        v01_cnt = count_rule("V01")
        v02_cnt = count_rule("V02")
        v03_cnt = count_rule("V03")
        v04_cnt = count_rule("V04")
        v05_cnt = count_rule("V05")

        return DashboardSummary(
            total_documents=total_docs,
            clean_documents=clean_docs,
            flagged_documents=flagged_docs,
            pending_review_documents=pending_review_docs,
            low_confidence_documents=v05_cnt,
            total_value=float(total_val_dec),
            duplicate_count=dup_docs,
            v01_count=v01_cnt,
            v02_count=v02_cnt,
            v03_count=v03_cnt,
            v04_count=v04_cnt,
            v05_count=v05_cnt,
        )


def delete_all_documents():
    """Clear all records from database for clean test resets."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM review_actions;")
        cursor.execute("DELETE FROM validation_flags;")
        cursor.execute("DELETE FROM audit_runs;")
        cursor.execute("DELETE FROM extractions;")
        cursor.execute("DELETE FROM audit_flags;")
        cursor.execute("DELETE FROM line_items;")
        cursor.execute("DELETE FROM documents;")


# =========================================================================
# User Account, Authentication & Verification Repository Functions
# =========================================================================

def create_user(
    identifier: str,
    password_hash: str,
    full_name: Optional[str] = None,
    is_verified: bool = False,
    term_pref: str = "Fall 2026",
) -> dict:
    """Create a new user account with identifier (email or phone)."""
    user_id = str(uuid.uuid4())
    now_iso = datetime.now(timezone.utc).isoformat()
    is_email = "@" in identifier
    email = identifier if is_email else None
    phone = identifier if not is_email else None
    settings_dict = {"academic_term_preference": term_pref}

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO users (id, identifier, email, phone, full_name, password_hash, is_verified, created_at, updated_at, settings_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                user_id,
                identifier.strip().lower(),
                email.strip().lower() if email else None,
                phone.strip() if phone else None,
                full_name.strip() if full_name else None,
                password_hash,
                1 if is_verified else 0,
                now_iso,
                now_iso,
                json.dumps(settings_dict),
            ),
        )

    return get_user_by_id(user_id)  # type: ignore


def get_user_by_id(user_id: str) -> Optional[dict]:
    """Retrieve user dictionary by user ID."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE id = ?;", (user_id,))
        row = cursor.fetchone()
        if not row:
            return None
        settings_dict = {}
        if row["settings_json"]:
            try:
                settings_dict = json.loads(row["settings_json"])
            except Exception:
                pass
        return {
            "id": row["id"],
            "identifier": row["identifier"],
            "email": row["email"],
            "phone": row["phone"],
            "full_name": row["full_name"],
            "password_hash": row["password_hash"],
            "is_verified": bool(row["is_verified"]),
            "created_at": row["created_at"],
            "academic_term_preference": settings_dict.get("academic_term_preference", "Fall 2026"),
        }


def get_user_by_identifier(identifier: str) -> Optional[dict]:
    """Retrieve user dictionary by identifier (email or phone)."""
    clean_id = identifier.strip().lower()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM users WHERE identifier = ? OR email = ? OR phone = ?;",
            (clean_id, clean_id, clean_id),
        )
        row = cursor.fetchone()
        if not row:
            return None
        settings_dict = {}
        if row["settings_json"]:
            try:
                settings_dict = json.loads(row["settings_json"])
            except Exception:
                pass
        return {
            "id": row["id"],
            "identifier": row["identifier"],
            "email": row["email"],
            "phone": row["phone"],
            "full_name": row["full_name"],
            "password_hash": row["password_hash"],
            "is_verified": bool(row["is_verified"]),
            "created_at": row["created_at"],
            "academic_term_preference": settings_dict.get("academic_term_preference", "Fall 2026"),
        }


def verify_user(identifier: str) -> bool:
    """Mark a user account as verified."""
    clean_id = identifier.strip().lower()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE users SET is_verified = 1, updated_at = ? WHERE identifier = ? OR email = ? OR phone = ?;",
            (datetime.now(timezone.utc).isoformat(), clean_id, clean_id, clean_id),
        )
        return cursor.rowcount > 0


def update_user_password(user_id: str, new_password_hash: str) -> bool:
    """Update user password hash."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE users SET password_hash = ?, updated_at = ? WHERE id = ?;",
            (new_password_hash, datetime.now(timezone.utc).isoformat(), user_id),
        )
        return cursor.rowcount > 0


def update_user_profile(user_id: str, full_name: Optional[str] = None, term_pref: Optional[str] = None) -> Optional[dict]:
    """Update user profile fields and term preferences."""
    user = get_user_by_id(user_id)
    if not user:
        return None
    effective_name = full_name if full_name is not None else user["full_name"]
    effective_term = term_pref if term_pref is not None else user["academic_term_preference"]
    settings_dict = {"academic_term_preference": effective_term}

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE users
            SET full_name = ?, settings_json = ?, updated_at = ?
            WHERE id = ?;
            """,
            (effective_name, json.dumps(settings_dict), datetime.now(timezone.utc).isoformat(), user_id),
        )
    return get_user_by_id(user_id)


def delete_user_account(user_id: str) -> bool:
    """Completely purge a user account, sessions, and all owned documents/files."""
    # 1. Purge all user data & files
    reset_user_data(user_id)

    with get_db_connection() as conn:
        cursor = conn.cursor()
        # 2. Delete sessions
        cursor.execute("DELETE FROM user_sessions WHERE user_id = ?;", (user_id,))
        cursor.execute("DELETE FROM sessions WHERE user_id = ?;", (user_id,))
        # 3. Delete user row
        cursor.execute("DELETE FROM users WHERE id = ?;", (user_id,))
        return cursor.rowcount > 0


# =========================================================================
# Verification Code Storage & Verification
# =========================================================================

def save_verification_code(identifier: str, code_hash: str, purpose: str, expires_minutes: int = 15):
    """Store verification code hash with expiration timestamp."""
    clean_id = identifier.strip().lower()
    now = datetime.now(timezone.utc)
    expires_at = (now + timedelta(minutes=expires_minutes)).isoformat()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        # Invalidate older pending codes for same identifier & purpose
        cursor.execute("DELETE FROM verification_codes WHERE identifier = ? AND purpose = ?;", (clean_id, purpose))
        cursor.execute(
            """
            INSERT INTO verification_codes (identifier, code_hash, purpose, expires_at, created_at)
            VALUES (?, ?, ?, ?, ?);
            """,
            (clean_id, code_hash, purpose, expires_at, now.isoformat()),
        )


def check_verification_code(identifier: str, code_hash: str, purpose: str) -> bool:
    """Verify code hash and expiry, then invalidate on success."""
    clean_id = identifier.strip().lower()
    now_iso = datetime.now(timezone.utc).isoformat()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id FROM verification_codes
            WHERE identifier = ? AND code_hash = ? AND purpose = ? AND expires_at > ?;
            """,
            (clean_id, code_hash, purpose, now_iso),
        )
        row = cursor.fetchone()
        if not row:
            return False
        # Consume code once verified
        cursor.execute("DELETE FROM verification_codes WHERE id = ?;", (row["id"],))
        return True


# =========================================================================
# Session Management
# =========================================================================

def create_session(user_id: str, token: str, expires_hours: int = 72) -> str:
    """Create a persistent user session with token hash in user_sessions and legacy sessions."""
    session_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    expires_at = (now + timedelta(hours=expires_hours)).isoformat()
    t_hash = hash_token(token)

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO user_sessions (id, user_id, token_hash, created_at, expires_at, revoked_at)
            VALUES (?, ?, ?, ?, ?, NULL);
            """,
            (session_id, user_id, t_hash, now.isoformat(), expires_at),
        )
        cursor.execute(
            """
            INSERT INTO sessions (id, user_id, token, expires_at, created_at)
            VALUES (?, ?, ?, ?, ?);
            """,
            (session_id, user_id, token, expires_at, now.isoformat()),
        )
    return token


def get_session_user(token: str) -> Optional[dict]:
    """Retrieve authenticated user by session token if not expired and not revoked."""
    now_iso = datetime.now(timezone.utc).isoformat()
    t_hash = hash_token(token)
    with get_db_connection() as conn:
        cursor = conn.cursor()
        # Query canonical user_sessions table first
        cursor.execute(
            """
            SELECT u.*, s.expires_at FROM user_sessions s
            JOIN users u ON s.user_id = u.id
            WHERE s.token_hash = ? AND s.revoked_at IS NULL AND s.expires_at > ?;
            """,
            (t_hash, now_iso),
        )
        row = cursor.fetchone()
        if not row:
            # Fallback to legacy sessions table
            cursor.execute(
                """
                SELECT u.*, s.expires_at FROM sessions s
                JOIN users u ON s.user_id = u.id
                WHERE s.token = ? AND s.expires_at > ?;
                """,
                (token, now_iso),
            )
            row = cursor.fetchone()
        if not row:
            return None
        settings_dict = {}
        if row["settings_json"]:
            try:
                settings_dict = json.loads(row["settings_json"])
            except Exception:
                pass
        return {
            "id": row["id"],
            "identifier": row["identifier"],
            "email": row["email"],
            "phone": row["phone"],
            "full_name": row["full_name"],
            "password_hash": row["password_hash"],
            "is_verified": bool(row["is_verified"]),
            "created_at": row["created_at"],
            "academic_term_preference": settings_dict.get("academic_term_preference", "Fall 2026"),
        }


def delete_session(token: str) -> bool:
    """Invalidate session token by revoking in user_sessions and deleting from sessions."""
    now_iso = datetime.now(timezone.utc).isoformat()
    t_hash = hash_token(token)
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE user_sessions SET revoked_at = ? WHERE token_hash = ?;", (now_iso, t_hash))
        cursor.execute("DELETE FROM sessions WHERE token = ?;", (token,))
        return cursor.rowcount > 0


def delete_all_user_sessions(user_id: str) -> bool:
    """Invalidate all sessions for user."""
    now_iso = datetime.now(timezone.utc).isoformat()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE user_sessions SET revoked_at = ? WHERE user_id = ?;", (now_iso, user_id))
        cursor.execute("DELETE FROM sessions WHERE user_id = ?;", (user_id,))
        return cursor.rowcount > 0


def delete_all_auth_data():
    """Clear all non-system users, sessions, and verification codes (useful for test resets)."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM verification_codes;")
        cursor.execute("DELETE FROM user_sessions;")
        cursor.execute("DELETE FROM sessions;")
        cursor.execute("DELETE FROM users WHERE id != 'system_default';")
