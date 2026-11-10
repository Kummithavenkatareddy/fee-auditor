import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.db.session import init_db
from app.db.repository import delete_all_documents, get_all_documents
from app.services.extractor import extract_document
from app.services.validator import apply_all_validation_rules
from app.schemas.document import DocumentExtraction, ExtractedField, ExtractedLineItem

client = TestClient(app)

SAMPLES_DIR = Path(__file__).resolve().parent.parent / "synthetic_data" / "samples"
GROUND_TRUTH_PATH = Path(__file__).resolve().parent.parent / "synthetic_data" / "ground_truth.json"


@pytest.fixture(autouse=True)
def setup_and_teardown():
    init_db()
    delete_all_documents()
    yield
    delete_all_documents()


def get_ground_truth():
    with open(GROUND_TRUTH_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


# ============================================================================
# TEST A1: Clean invoice extraction
# ============================================================================
def test_a1_clean_invoice_extraction():
    """A1: Verify clean receipt/invoice extraction and field extraction."""
    # Test canonical clean invoice 1 (INR) or legacy membership invoice 3
    if (SAMPLES_DIR / "INV-001.pdf").exists():
        clean_file = SAMPLES_DIR / "INV-001.pdf"
        filename = "INV-001.pdf"
        expected_total = 9794.00
    else:
        clean_file = SAMPLES_DIR / "clean_library_membership_invoice_3.pdf"
        filename = "clean_library_membership_invoice_3.pdf"
        expected_total = 472.50

    assert clean_file.exists(), f"Sample file {clean_file} does not exist"

    content = clean_file.read_bytes()
    # Live Azure extraction
    extracted = extract_document(file_bytes=content, filename=filename)

    # Validate
    validated = apply_all_validation_rules(extracted)

    # Assertions: clean financial reconciliation
    v01_flags = [f for f in validated.validation_flags if f.rule_id == "V01"]
    assert len(v01_flags) == 0
    assert validated.vendor_name.value is not None
    assert validated.vendor_name.confidence is not None
    assert validated.vendor_name.confidence >= 0.85

    assert validated.total.value is not None
    assert abs(float(validated.total.value) - expected_total) < 0.05
    assert validated.total.confidence is not None
    assert validated.total.confidence >= 0.85

    assert validated.vendor_tax_id.value is not None


# ============================================================================
# TEST A2: Total mismatch and missing tax number/date validation
# ============================================================================
def test_a2_total_mismatch_and_missing_tax_validation():
    """A2: Verify V01 Total Mismatch, V02 Missing Tax Number, and V04 Outside Academic Term."""
    # 1. Total Mismatch (V01)
    if (SAMPLES_DIR / "INV-004.pdf").exists():
        mismatch_file = SAMPLES_DIR / "INV-004.pdf"
        filename_mismatch = "INV-004.pdf"
        expected_discrepancy = "4000.00"
    else:
        mismatch_file = SAMPLES_DIR / "mismatch_equipment_invoice_4.pdf"
        filename_mismatch = "mismatch_equipment_invoice_4.pdf"
        expected_discrepancy = "80.00"

    content_mismatch = mismatch_file.read_bytes()
    doc_mismatch = extract_document(file_bytes=content_mismatch, filename=filename_mismatch)
    val_mismatch = apply_all_validation_rules(doc_mismatch)

    assert val_mismatch.audit_status == "flagged"
    mismatch_flag = next((f for f in val_mismatch.validation_flags if f.rule_id == "V01"), None)
    assert mismatch_flag is not None
    assert mismatch_flag.severity == "CRITICAL"
    assert expected_discrepancy in mismatch_flag.reason

    # 2. Missing Tax Number (V02)
    if (SAMPLES_DIR / "INV-005.pdf").exists():
        missing_tax_file = SAMPLES_DIR / "INV-005.pdf"
        filename_missing = "INV-005.pdf"
    else:
        missing_tax_file = SAMPLES_DIR / "missing_tax_seminar_invoice_5.pdf"
        filename_missing = "missing_tax_seminar_invoice_5.pdf"

    content_missing_tax = missing_tax_file.read_bytes()
    doc_missing_tax = extract_document(file_bytes=content_missing_tax, filename=filename_missing)
    val_missing_tax = apply_all_validation_rules(doc_missing_tax)

    assert val_missing_tax.audit_status == "flagged"
    v02_flag = next((f for f in val_missing_tax.validation_flags if f.rule_id == "V02"), None)
    assert v02_flag is not None
    assert v02_flag.severity == "MEDIUM"
    assert v02_flag.field_name == "vendor_tax_id"
    assert "missing" in v02_flag.reason.lower()

    # 3. Outside Academic Term (V04)
    if (SAMPLES_DIR / "REC-006.pdf").exists():
        out_of_term_file = SAMPLES_DIR / "REC-006.pdf"
        filename_out_of_term = "REC-006.pdf"
        expected_date = "2027-01-15"
    else:
        out_of_term_file = SAMPLES_DIR / "out_of_term_software_invoice_6.pdf"
        filename_out_of_term = "out_of_term_software_invoice_6.pdf"
        expected_date = "2026-05-15"

    content_out_of_term = out_of_term_file.read_bytes()
    doc_out_of_term = extract_document(file_bytes=content_out_of_term, filename=filename_out_of_term)
    val_out_of_term = apply_all_validation_rules(doc_out_of_term)

    assert val_out_of_term.audit_status == "flagged"
    v04_flag = next((f for f in val_out_of_term.validation_flags if f.rule_id == "V04"), None)
    assert v04_flag is not None
    assert v04_flag.severity == "MEDIUM"
    assert v04_flag.field_name == "invoice_date"
    assert expected_date in v04_flag.actual_value or expected_date in v04_flag.reason


# ============================================================================
# TEST A3: Duplicate upload and low-confidence highlighting
# ============================================================================
def test_a3_duplicate_upload_and_low_confidence():
    """A3: Verify duplicate invoice detection (exact hash and invoice number) and low confidence flagging."""
    # Test Duplicate Detection via API batch endpoint
    if (SAMPLES_DIR / "INV-001.pdf").exists():
        file1 = SAMPLES_DIR / "INV-001.pdf"
    elif (SAMPLES_DIR / "clean_campus_store_receipt_2.pdf").exists():
        file1 = SAMPLES_DIR / "clean_campus_store_receipt_2.pdf"
    else:
        file1 = list(SAMPLES_DIR.glob("*.pdf"))[0]

    # Batch 1: Upload clean document
    with open(file1, "rb") as f:
        res1 = client.post(
            "/api/audit/upload",
            files=[("files", ("first_upload.pdf", f.read(), "application/pdf"))],
        )
    assert res1.status_code == 200
    data1 = res1.json()
    assert data1["successful_extractions"] == 1
    doc1 = data1["documents"][0]
    assert doc1["is_duplicate"] is False

    # Batch 2: Exact duplicate re-upload (same file content)
    with open(file1, "rb") as f:
        res2 = client.post(
            "/api/audit/upload",
            files=[("files", ("second_upload.pdf", f.read(), "application/pdf"))],
        )
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["duplicate_files"] == 1
    assert len(data2["duplicates"]) == 1
    dup2 = data2["duplicates"][0]
    assert dup2["is_duplicate"] is True
    assert dup2["is_exact_duplicate"] is True
    assert dup2["duplicate_type"] == "exact"
    assert dup2["existing_document_id"] == doc1["id"]
    assert "Exact duplicate document detected" in dup2["message"]

    # Test Low-Confidence Flagging (V05)
    doc_low_conf = DocumentExtraction(
        file_name="low_confidence_sample.pdf",
        file_hash="hash_low_conf_test",
        model_used="prebuilt-invoice",
        document_type="invoice",
        vendor_name=ExtractedField(value="Doubtful Vendor", confidence=0.72),  # < 0.85
        invoice_id=ExtractedField(value="INV-LOW-99", confidence=0.80),        # < 0.85
        invoice_date=ExtractedField(value="2026-09-20", confidence=0.95),
        vendor_tax_id=ExtractedField(value="TAX-998877", confidence=0.95),
        subtotal=ExtractedField(value="100.00", confidence=0.95),
        tax=ExtractedField(value="10.00", confidence=0.95),
        total=ExtractedField(value="110.00", confidence=0.60),                 # < 0.85
        line_items=[],
    )

    validated_low_conf = apply_all_validation_rules(doc_low_conf)
    assert validated_low_conf.audit_status == "flagged"
    v05_flags = [f for f in validated_low_conf.validation_flags if f.rule_id == "V05"]
    assert len(v05_flags) >= 3  # vendor_name, invoice_id, total all < 0.85
    flagged_fields = [f.field_name for f in v05_flags]
    assert "vendor_name" in flagged_fields
    assert "invoice_id" in flagged_fields
    assert "total" in flagged_fields

