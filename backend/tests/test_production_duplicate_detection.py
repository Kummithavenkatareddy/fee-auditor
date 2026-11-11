import io
import hashlib
import uuid
import threading
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest
from fastapi.testclient import TestClient

import pypdf

from app.main import app
from app.config import settings
from app.db.session import init_db, get_db_connection
from app.db.repository import (
    get_document_by_id,
    get_document_by_hash,
    delete_all_documents,
    delete_all_auth_data,
    update_manual_review,
)
from app.services.auth_security import reset_rate_limits
from app.schemas.common import FieldStatus, ExtractedField, ExtractedLineItem, ValidationFlag
from app.schemas.document import DocumentExtraction
from app.services.audit_orchestrator import orchestrator

client = TestClient(app)
SAMPLES_DIR = Path(__file__).resolve().parent.parent / "synthetic_data" / "samples"


def register_and_login_user(identifier: str, password: str = "SecurePass123!") -> dict:
    """Helper to register and verify a test user, returning auth headers."""
    reg = client.post("/api/auth/register", json={"identifier": identifier, "password": password})
    code = reg.json().get("dev_verification_code") or "927824"
    ver = client.post("/api/auth/verify", json={"identifier": identifier, "code": code})
    token = ver.json()["access_token"]
    return {
        "headers": {"Authorization": f"Bearer {token}"},
        "user": ver.json()["user"],
    }


def make_synthetic_pdf_bytes(label: str = "doc") -> bytes:
    """Generate valid PDF binary payload with unique content."""
    writer = pypdf.PdfWriter()
    writer.add_blank_page(width=72, height=72)
    writer.add_metadata({"/Title": f"{label}_{uuid.uuid4()}"})
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def make_mock_extraction(
    filename: str,
    file_bytes: bytes,
    vendor_name: str,
    invoice_id: str,
    total: str = "1000.00",
    subtotal: str = "900.00",
    tax: str = "100.00",
    doc_type: str = "invoice",
) -> DocumentExtraction:
    file_hash = hashlib.sha256(file_bytes).hexdigest()
    return DocumentExtraction(
        file_name=filename,
        file_hash=file_hash,
        document_type=doc_type,
        model_used="prebuilt-invoice" if doc_type == "invoice" else "prebuilt-receipt",
        vendor_name=ExtractedField(value=vendor_name, confidence=0.98),
        invoice_id=ExtractedField(value=invoice_id, confidence=0.98),
        invoice_date=ExtractedField(value="2026-09-15", confidence=0.98),
        vendor_tax_id=ExtractedField(value="27AABCU9603R1ZX", confidence=0.98),
        subtotal=ExtractedField(value=subtotal, confidence=0.98),
        tax=ExtractedField(value=tax, confidence=0.98),
        total=ExtractedField(value=total, confidence=0.98),
        line_items=[
            ExtractedLineItem(item_index=1, description="Item 1", amount=subtotal, confidence=0.98)
        ],
    )


@pytest.fixture(autouse=True)
def setup_clean_db():
    client.cookies.clear()
    init_db()
    delete_all_documents()
    delete_all_auth_data()
    reset_rate_limits()
    yield
    client.cookies.clear()
    delete_all_documents()
    delete_all_auth_data()
    reset_rate_limits()


# ============================================================================
# SCENARIO 1: Exact same PDF uploaded twice by the same user
# Level 1 duplicate response, no new DB record, Azure NOT called.
# ============================================================================
def test_scenario_1_exact_same_pdf_uploaded_twice_by_same_user():
    user = register_and_login_user("dup_user_1@university.edu")
    pdf_bytes = make_synthetic_pdf_bytes("tuition_original")

    mock_doc = make_mock_extraction(
        filename="tuition_receipt_1.pdf",
        file_bytes=pdf_bytes,
        vendor_name="University Fee Office",
        invoice_id="UF-2026-001",
    )

    with patch("app.services.audit_orchestrator.extract_document", return_value=mock_doc) as mock_extract:
        # 1. First upload: Brand new document
        res1 = client.post(
            "/api/audit/upload",
            headers=user["headers"],
            files=[("files", ("tuition_receipt_1.pdf", pdf_bytes, "application/pdf"))],
        )
        assert res1.status_code == 200
        data1 = res1.json()
        assert data1["successful_extractions"] == 1
        assert data1["duplicate_files"] == 0
        assert len(data1["documents"]) == 1
        doc1_id = data1["documents"][0]["id"]
        assert mock_extract.call_count == 1

        # 2. Second upload: Identical file bytes
        res2 = client.post(
            "/api/audit/upload",
            headers=user["headers"],
            files=[("files", ("tuition_receipt_1.pdf", pdf_bytes, "application/pdf"))],
        )
        assert res2.status_code == 200
        data2 = res2.json()

        # Azure must NOT be called on exact duplicate!
        assert mock_extract.call_count == 1, "Azure extract_document must NOT be called for exact file duplicate"

        # Level 1 Duplicate Response assertions
        assert data2["duplicate_files"] == 1
        assert data2["successful_extractions"] == 0
        assert len(data2["documents"]) == 0
        assert len(data2["duplicates"]) == 1

        dup = data2["duplicates"][0]
        assert dup["is_duplicate"] is True
        assert dup["is_exact_duplicate"] is True
        assert dup["duplicate_type"] == "exact"
        assert dup["existing_document_id"] == doc1_id
        assert dup["existing_file_name"] == "tuition_receipt_1.pdf"
        assert "Exact duplicate document detected" in dup["message"]

        # Confirm no new DB record created in SQLite
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT count(*) as cnt FROM documents WHERE owner_user_id = ?;", (user["user"]["id"],))
            assert cursor.fetchone()["cnt"] == 1


# ============================================================================
# SCENARIO 2: Same PDF uploaded with different filename (detected via SHA-256)
# ============================================================================
def test_scenario_2_same_pdf_different_filename_detected_via_sha256():
    user = register_and_login_user("dup_user_2@university.edu")
    pdf_bytes = make_synthetic_pdf_bytes("stationary_bill")

    mock_doc = make_mock_extraction(
        filename="stationary_bill_august.pdf",
        file_bytes=pdf_bytes,
        vendor_name="National Book Depot",
        invoice_id="NBD-4402",
    )

    with patch("app.services.audit_orchestrator.extract_document", return_value=mock_doc) as mock_extract:
        # First upload
        res1 = client.post(
            "/api/audit/upload",
            headers=user["headers"],
            files=[("files", ("stationary_bill_august.pdf", pdf_bytes, "application/pdf"))],
        )
        doc1_id = res1.json()["documents"][0]["id"]
        assert mock_extract.call_count == 1

        # Second upload with completely different filename
        res2 = client.post(
            "/api/audit/upload",
            headers=user["headers"],
            files=[("files", ("re_scanned_copy_of_bill_FINAL.pdf", pdf_bytes, "application/pdf"))],
        )
        assert res2.status_code == 200
        data2 = res2.json()

        assert mock_extract.call_count == 1
        assert data2["duplicate_files"] == 1
        dup = data2["duplicates"][0]
        assert dup["is_exact_duplicate"] is True
        assert dup["existing_document_id"] == doc1_id
        assert dup["existing_file_name"] == "stationary_bill_august.pdf"
        assert dup["filename"] == "re_scanned_copy_of_bill_FINAL.pdf"


# ============================================================================
# SCENARIO 3: Same invoice represented by different PDF (Level 2 Logical Duplicate)
# Different SHA-256 hash, same vendor + invoice number -> V03 flag recorded & linked
# ============================================================================
def test_scenario_3_level_2_logical_duplicate_same_vendor_and_invoice_id():
    user = register_and_login_user("dup_user_3@university.edu")
    pdf_bytes_1 = make_synthetic_pdf_bytes("invoice_scan_a")
    pdf_bytes_2 = make_synthetic_pdf_bytes("invoice_scan_b_different_bytes")

    # Ensure binary hashes differ
    assert hashlib.sha256(pdf_bytes_1).hexdigest() != hashlib.sha256(pdf_bytes_2).hexdigest()

    mock_doc1 = make_mock_extraction(
        filename="invoice_scan_1.pdf",
        file_bytes=pdf_bytes_1,
        vendor_name="Apex Lab Equipment Pvt Ltd",
        invoice_id="APEX-2026-901",
        subtotal="4000.00",
        tax="500.00",
        total="4500.00",
    )
    mock_doc2 = make_mock_extraction(
        filename="invoice_scan_2.pdf",
        file_bytes=pdf_bytes_2,
        vendor_name="Apex Lab Equipment",  # Normalized matches Apex Lab Equipment Pvt Ltd
        invoice_id="apex-2026-901",       # Normalized matches APEX2026901
        subtotal="4000.00",
        tax="500.00",
        total="4500.00",
    )

    with patch("app.services.audit_orchestrator.extract_document", side_effect=[mock_doc1, mock_doc2]) as mock_extract:
        # First upload
        res1 = client.post(
            "/api/audit/upload",
            headers=user["headers"],
            files=[("files", ("invoice_scan_1.pdf", pdf_bytes_1, "application/pdf"))],
        )
        assert res1.status_code == 200
        doc1 = res1.json()["documents"][0]
        assert doc1["is_duplicate"] is False
        assert doc1["audit_status"] == "clean"

        # Second upload with different scan of identical business invoice
        res2 = client.post(
            "/api/audit/upload",
            headers=user["headers"],
            files=[("files", ("invoice_scan_2.pdf", pdf_bytes_2, "application/pdf"))],
        )
        assert res2.status_code == 200
        data2 = res2.json()

        assert mock_extract.call_count == 2
        assert data2["successful_extractions"] == 1
        doc2 = data2["documents"][0]

        # Verify Level 2 business duplicate
        assert doc2["is_business_duplicate"] is True
        assert doc2["is_duplicate"] is True
        assert doc2["is_exact_duplicate"] is False
        assert doc2["audit_status"] == "flagged"
        assert doc2["matched_document_id"] == doc1["id"]

        # Verify V03 validation flag details
        v03 = next((f for f in doc2["validation_flags"] if f["rule_id"] == "V03"), None)
        assert v03 is not None
        assert v03["rule_name"] == "Duplicate Invoice (Business Identifier)"
        assert v03["severity"] == "CRITICAL"
        assert doc1["id"] in v03["reason"]
        assert doc1["file_name"] in v03["reason"]

        # Confirm BOTH documents are persisted in SQLite and storage
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT count(*) as cnt FROM documents WHERE owner_user_id = ?;", (user["user"]["id"],))
            assert cursor.fetchone()["cnt"] == 2


# ============================================================================
# SCENARIO 4: Different invoices from same vendor -> Clean, no duplicate flag
# ============================================================================
def test_scenario_4_different_invoices_same_vendor_clean():
    user = register_and_login_user("dup_user_4@university.edu")
    pdf_bytes_1 = make_synthetic_pdf_bytes("vendor_inv_1")
    pdf_bytes_2 = make_synthetic_pdf_bytes("vendor_inv_2")

    mock_doc1 = make_mock_extraction(
        filename="bill_1.pdf",
        file_bytes=pdf_bytes_1,
        vendor_name="Acme Scientific Supplies",
        invoice_id="ACME-001",
    )
    mock_doc2 = make_mock_extraction(
        filename="bill_2.pdf",
        file_bytes=pdf_bytes_2,
        vendor_name="Acme Scientific Supplies",
        invoice_id="ACME-002",  # Different invoice number
    )

    with patch("app.services.audit_orchestrator.extract_document", side_effect=[mock_doc1, mock_doc2]):
        res1 = client.post(
            "/api/audit/upload",
            headers=user["headers"],
            files=[("files", ("bill_1.pdf", pdf_bytes_1, "application/pdf"))],
        )
        assert res1.json()["documents"][0]["audit_status"] == "clean"

        res2 = client.post(
            "/api/audit/upload",
            headers=user["headers"],
            files=[("files", ("bill_2.pdf", pdf_bytes_2, "application/pdf"))],
        )
        doc2 = res2.json()["documents"][0]
        assert doc2["is_duplicate"] is False
        assert doc2["is_business_duplicate"] is False
        assert doc2["audit_status"] == "clean"
        assert not any(f["rule_id"] == "V03" for f in doc2["validation_flags"])


# ============================================================================
# SCENARIO 5: Same invoice number from different vendors -> Clean, no duplicate flag
# ============================================================================
def test_scenario_5_same_invoice_id_different_vendors_clean():
    user = register_and_login_user("dup_user_5@university.edu")
    pdf_bytes_1 = make_synthetic_pdf_bytes("vendor_a")
    pdf_bytes_2 = make_synthetic_pdf_bytes("vendor_b")

    mock_doc1 = make_mock_extraction(
        filename="vendor_a_inv.pdf",
        file_bytes=pdf_bytes_1,
        vendor_name="Global Tech Summit Inc",
        invoice_id="INV-2026-100",
    )
    mock_doc2 = make_mock_extraction(
        filename="vendor_b_inv.pdf",
        file_bytes=pdf_bytes_2,
        vendor_name="City Hardware Distributors",  # Different vendor
        invoice_id="INV-2026-100",  # Same invoice ID
    )

    with patch("app.services.audit_orchestrator.extract_document", side_effect=[mock_doc1, mock_doc2]):
        res1 = client.post(
            "/api/audit/upload",
            headers=user["headers"],
            files=[("files", ("vendor_a_inv.pdf", pdf_bytes_1, "application/pdf"))],
        )
        assert res1.json()["documents"][0]["audit_status"] == "clean"

        res2 = client.post(
            "/api/audit/upload",
            headers=user["headers"],
            files=[("files", ("vendor_b_inv.pdf", pdf_bytes_2, "application/pdf"))],
        )
        doc2 = res2.json()["documents"][0]
        assert doc2["is_duplicate"] is False
        assert doc2["is_business_duplicate"] is False
        assert doc2["audit_status"] == "clean"
        assert not any(f["rule_id"] == "V03" for f in doc2["validation_flags"])


# ============================================================================
# SCENARIO 6: Same file uploaded by User A and User B -> Complete isolation
# ============================================================================
def test_scenario_6_multi_user_isolation_same_file():
    user_a = register_and_login_user("user_a_duptest@university.edu")
    user_b = register_and_login_user("user_b_duptest@university.edu")
    shared_pdf_bytes = make_synthetic_pdf_bytes("shared_document")

    mock_doc_a = make_mock_extraction(
        filename="course_fee.pdf",
        file_bytes=shared_pdf_bytes,
        vendor_name="Engineering Faculty",
        invoice_id="ENG-9901",
    )
    mock_doc_b = make_mock_extraction(
        filename="course_fee.pdf",
        file_bytes=shared_pdf_bytes,
        vendor_name="Engineering Faculty",
        invoice_id="ENG-9901",
    )

    with patch("app.services.audit_orchestrator.extract_document", side_effect=[mock_doc_a, mock_doc_b]) as mock_extract:
        # User A uploads document
        res_a = client.post(
            "/api/audit/upload",
            headers=user_a["headers"],
            files=[("files", ("course_fee.pdf", shared_pdf_bytes, "application/pdf"))],
        )
        assert res_a.status_code == 200
        data_a = res_a.json()
        assert data_a["successful_extractions"] == 1
        assert data_a["duplicate_files"] == 0
        doc_a_id = data_a["documents"][0]["id"]

        # User B uploads exact same file: must NOT be flagged as duplicate!
        res_b = client.post(
            "/api/audit/upload",
            headers=user_b["headers"],
            files=[("files", ("course_fee.pdf", shared_pdf_bytes, "application/pdf"))],
        )
        assert res_b.status_code == 200
        data_b = res_b.json()

        # User B gets fresh extraction and own document record
        assert data_b["successful_extractions"] == 1
        assert data_b["duplicate_files"] == 0
        doc_b = data_b["documents"][0]
        assert doc_b["id"] != doc_a_id
        assert doc_b["is_duplicate"] is False
        assert doc_b["is_exact_duplicate"] is False
        assert mock_extract.call_count == 2

        # Verify DB records are completely isolated
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT owner_user_id FROM documents WHERE id = ?;", (doc_a_id,))
            assert cursor.fetchone()["owner_user_id"] == user_a["user"]["id"]
            cursor.execute("SELECT owner_user_id FROM documents WHERE id = ?;", (doc_b["id"],))
            assert cursor.fetchone()["owner_user_id"] == user_b["user"]["id"]


# ============================================================================
# SCENARIO 7: Batch upload with mix of clean, duplicate, and invalid files
# ============================================================================
def test_scenario_7_batch_upload_mix_clean_duplicate_and_invalid():
    user = register_and_login_user("dup_user_7@university.edu")
    pdf_clean = make_synthetic_pdf_bytes("batch_clean")
    pdf_existing = make_synthetic_pdf_bytes("batch_existing")

    # Ingest baseline document first
    mock_base = make_mock_extraction(
        filename="existing_file.pdf",
        file_bytes=pdf_existing,
        vendor_name="University Books",
        invoice_id="UB-001",
    )
    with patch("app.services.audit_orchestrator.extract_document", return_value=mock_base):
        client.post(
            "/api/audit/upload",
            headers=user["headers"],
            files=[("files", ("existing_file.pdf", pdf_existing, "application/pdf"))],
        )

    # Now upload a batch containing:
    # 1. New clean file
    # 2. Exact duplicate of existing_file.pdf
    # 3. Invalid empty file
    mock_clean = make_mock_extraction(
        filename="new_clean_file.pdf",
        file_bytes=pdf_clean,
        vendor_name="Office Supplies Co",
        invoice_id="OS-501",
    )
    with patch("app.services.audit_orchestrator.extract_document", return_value=mock_clean) as mock_extract:
        res = client.post(
            "/api/audit/upload",
            headers=user["headers"],
            files=[
                ("files", ("new_clean_file.pdf", pdf_clean, "application/pdf")),
                ("files", ("re_upload_duplicate.pdf", pdf_existing, "application/pdf")),
                ("files", ("invalid_empty.pdf", b"", "application/pdf")),
            ],
        )
        assert res.status_code == 200
        data = res.json()

        assert data["total_files"] == 3
        assert data["successful_extractions"] == 1
        assert data["duplicate_files"] == 1
        assert data["failed_extractions"] == 1

        # Clean file in documents
        assert len(data["documents"]) == 1
        assert data["documents"][0]["file_name"] == "new_clean_file.pdf"

        # Duplicate in duplicates
        assert len(data["duplicates"]) == 1
        assert data["duplicates"][0]["is_exact_duplicate"] is True
        assert data["duplicates"][0]["filename"] == "re_upload_duplicate.pdf"

        # Invalid in errors
        assert len(data["errors"]) == 1
        assert data["errors"][0]["file_name"] == "invalid_empty.pdf"

        # Azure only called for clean file
        assert mock_extract.call_count == 1


# ============================================================================
# SCENARIO 8: Concurrent uploads of identical files
# Handled gracefully without race conditions or duplicate records
# ============================================================================
def test_scenario_8_concurrent_uploads_of_identical_files():
    user = register_and_login_user("dup_user_8@university.edu")
    pdf_bytes = make_synthetic_pdf_bytes("concurrent_test")

    mock_doc = make_mock_extraction(
        filename="concurrent_tuition.pdf",
        file_bytes=pdf_bytes,
        vendor_name="Finance Dept",
        invoice_id="FIN-881",
    )

    results = []

    def upload_task(idx: int):
        with patch("app.services.audit_orchestrator.extract_document", return_value=mock_doc):
            res = client.post(
                "/api/audit/upload",
                headers=user["headers"],
                files=[("files", (f"concurrent_{idx}.pdf", pdf_bytes, "application/pdf"))],
            )
            return res.status_code, res.json()

    # Run 4 concurrent upload requests of the exact same file
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(upload_task, i) for i in range(4)]
        results = [f.result() for f in futures]

    status_codes = [r[0] for r in results]
    assert all(code == 200 for code in status_codes)

    # Exactly 1 request should have ingested, while 3 should have returned Level 1 duplicates
    new_doc_counts = sum(r[1]["successful_extractions"] for r in results)
    dup_counts = sum(r[1]["duplicate_files"] for r in results)

    assert new_doc_counts == 1, f"Expected exactly 1 new extraction, got {new_doc_counts}"
    assert dup_counts == 3, f"Expected 3 duplicate detections, got {dup_counts}"

    # Confirm exactly 1 record exists in SQLite
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT count(*) as cnt FROM documents WHERE owner_user_id = ?;", (user["user"]["id"],))
        assert cursor.fetchone()["cnt"] == 1


# ============================================================================
# SCENARIO 9: Existing document's audit history and records are NOT modified
# ============================================================================
def test_scenario_9_existing_document_audit_history_not_modified_on_duplicate():
    user = register_and_login_user("dup_user_9@university.edu")
    pdf_bytes = make_synthetic_pdf_bytes("preservation_test")

    mock_doc = make_mock_extraction(
        filename="initial_bill.pdf",
        file_bytes=pdf_bytes,
        vendor_name="Campus Medical Center",
        invoice_id="MED-2026-77",
    )

    with patch("app.services.audit_orchestrator.extract_document", return_value=mock_doc):
        res1 = client.post(
            "/api/audit/upload",
            headers=user["headers"],
            files=[("files", ("initial_bill.pdf", pdf_bytes, "application/pdf"))],
        )
        doc1_id = res1.json()["documents"][0]["id"]

    # Perform a manual review on document 1
    update_manual_review(
        doc_id=doc1_id,
        status="approved",
        notes="Reviewed by Senior Auditor: Valid verified clinical charges.",
        owner_user_id=user["user"]["id"],
    )

    # Capture original document state
    orig_doc = get_document_by_id(doc1_id, owner_user_id=user["user"]["id"])
    assert orig_doc.manual_review_status == "approved"
    assert orig_doc.manual_review_notes == "Reviewed by Senior Auditor: Valid verified clinical charges."
    orig_history = [dict(h) for h in orig_doc.audit_history]
    orig_history_len = len(orig_history)

    # Attempt duplicate upload of exact file
    with patch("app.services.audit_orchestrator.extract_document", side_effect=Exception("Should not be called!")):
        res2 = client.post(
            "/api/audit/upload",
            headers=user["headers"],
            files=[("files", ("duplicate_bill_attempt.pdf", pdf_bytes, "application/pdf"))],
        )
        assert res2.status_code == 200
        assert res2.json()["duplicate_files"] == 1

    # Verify original document was NOT modified
    after_doc = get_document_by_id(doc1_id, owner_user_id=user["user"]["id"])
    assert after_doc.manual_review_status == "approved"
    assert after_doc.manual_review_notes == "Reviewed by Senior Auditor: Valid verified clinical charges."
    assert len(after_doc.audit_history) == orig_history_len
    assert after_doc.audit_status == orig_doc.audit_status


# ============================================================================
# SCENARIO 10: Duplicate response includes valid link/reference to existing document
# ============================================================================
def test_scenario_10_duplicate_response_includes_valid_link_and_reference():
    user = register_and_login_user("dup_user_10@university.edu")
    pdf_bytes = make_synthetic_pdf_bytes("link_verification")

    mock_doc = make_mock_extraction(
        filename="original_contract.pdf",
        file_bytes=pdf_bytes,
        vendor_name="University Facilities",
        invoice_id="FAC-0099",
    )

    with patch("app.services.audit_orchestrator.extract_document", return_value=mock_doc):
        res1 = client.post(
            "/api/audit/upload",
            headers=user["headers"],
            files=[("files", ("original_contract.pdf", pdf_bytes, "application/pdf"))],
        )
        doc1_id = res1.json()["documents"][0]["id"]

    # Re-upload duplicate
    res2 = client.post(
        "/api/audit/upload",
        headers=user["headers"],
        files=[("files", ("copy_contract.pdf", pdf_bytes, "application/pdf"))],
    )
    assert res2.status_code == 200
    dup = res2.json()["duplicates"][0]

    # Verify reference
    assert dup["existing_document_id"] == doc1_id
    assert dup["existing_file_name"] == "original_contract.pdf"
    assert dup["document_url"] == f"/api/audit/documents/{doc1_id}"

    # Verify link is valid by fetching the referenced document via API
    get_res = client.get(dup["document_url"], headers=user["headers"])
    assert get_res.status_code == 200
    retrieved = get_res.json()
    assert retrieved["id"] == doc1_id
    assert retrieved["file_name"] == "original_contract.pdf"
