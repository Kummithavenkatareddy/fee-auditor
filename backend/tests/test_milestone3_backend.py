import io
import json
from decimal import Decimal
from datetime import date
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.common import FieldStatus, ExtractedField, ExtractedLineItem
from app.schemas.document import DocumentExtraction
from app.services.validator import (
    validate_v01_total_mismatch,
    validate_v02_missing_tax_number,
    validate_v03_duplicate_invoice,
    validate_v04_outside_academic_term,
    validate_v05_low_confidence,
    apply_all_validation_rules,
)
from app.services.audit_orchestrator import orchestrator
from app.db.session import init_db, get_db_connection
from app.db.repository import (
    save_document,
    get_document_by_id,
    delete_all_documents,
    update_manual_review,
    normalize_business_key,
)

client = TestClient(app)
SAMPLES_DIR = Path(__file__).resolve().parent.parent / "synthetic_data" / "samples"


@pytest.fixture(autouse=True)
def clean_db():
    init_db()
    delete_all_documents()
    yield
    delete_all_documents()


def make_mock_doc(
    doc_type="invoice",
    vendor_name="Apex Labs",
    tax_id="99-1010001",
    invoice_id="INV-001",
    invoice_date="2026-09-15",
    subtotal="100.00",
    tax="10.00",
    total="110.00",
    items=None,
    confidence=0.95,
    file_hash="hash_mock_001",
) -> DocumentExtraction:
    if items is None:
        items = [
            ExtractedLineItem(item_index=0, description="Item A", quantity="1.00", unit_price="60.00", amount="60.00", confidence=confidence),
            ExtractedLineItem(item_index=1, description="Item B", quantity="1.00", unit_price="40.00", amount="40.00", confidence=confidence),
        ]
    return DocumentExtraction(
        file_name="test_document.pdf",
        file_hash=file_hash,
        document_type=doc_type,
        model_used="prebuilt-invoice" if doc_type == "invoice" else "prebuilt-receipt",
        vendor_name=ExtractedField(value=vendor_name, confidence=confidence),
        vendor_tax_id=ExtractedField(
            value=tax_id,
            confidence=confidence if tax_id else None,
            status=FieldStatus.EXTRACTED if tax_id else (FieldStatus.NOT_APPLICABLE if doc_type == "receipt" else FieldStatus.MISSING),
        ),
        invoice_id=ExtractedField(
            value=invoice_id,
            confidence=confidence if invoice_id else None,
            status=FieldStatus.EXTRACTED if invoice_id else (FieldStatus.NOT_APPLICABLE if doc_type == "receipt" else FieldStatus.MISSING),
        ),
        invoice_date=ExtractedField(value=invoice_date, confidence=confidence),
        subtotal=ExtractedField(value=subtotal, confidence=confidence),
        tax=ExtractedField(value=tax, confidence=confidence),
        total=ExtractedField(value=total, confidence=confidence),
        line_items=items,
        created_at="2026-09-15T10:00:00Z",
    )


# ============================================================================
# TEST SUITE A1: Clean Invoices and Receipts
# ============================================================================
def test_a1_clean_invoice_and_receipt():
    """Verify clean invoice and receipt validation without false flags."""
    # 1. Clean Invoice (Tax-exclusive line items sum to subtotal + tax = total)
    clean_inv = make_mock_doc(
        doc_type="invoice",
        vendor_name="Cambridge Institute of Technology",
        tax_id="99-1010001",
        invoice_id="CIT-2026-901",
        invoice_date="2026-09-10",
        subtotal="1500.00",
        tax="0.00",
        total="1500.00",
        items=[
            ExtractedLineItem(item_index=0, description="Tuition Fee", amount="1200.00", confidence=0.95),
            ExtractedLineItem(item_index=1, description="Lab Access", amount="300.00", confidence=0.95),
        ],
        confidence=0.95,
    )
    val_inv = apply_all_validation_rules(clean_inv)
    assert val_inv.audit_status == "clean"
    assert len(val_inv.validation_flags) == 0

    # 2. Clean Receipt (No tax ID required, merchant name present, date in term)
    clean_rec = make_mock_doc(
        doc_type="receipt",
        vendor_name="Acropolis University Bookstore",
        tax_id=None,
        invoice_id=None,
        invoice_date="2026-10-05",
        subtotal="200.00",
        tax="16.00",
        total="216.00",
        items=[
            ExtractedLineItem(item_index=0, description="Handbook", amount="85.00", confidence=0.98),
            ExtractedLineItem(item_index=1, description="Calculator", amount="115.00", confidence=0.98),
        ],
        confidence=0.98,
    )
    val_rec = apply_all_validation_rules(clean_rec)
    assert val_rec.audit_status == "clean"
    # Receipts must NEVER trigger V02 (missing tax number)
    v02_flags = [f for f in val_rec.validation_flags if f.rule_id == "V02"]
    assert len(v02_flags) == 0


# ============================================================================
# TEST SUITE A2: Compliance Violations (V01, V02, V04)
# ============================================================================
def test_a2_compliance_violations():
    """Verify specific violation flags for V01, V02, and V04."""
    # 1. INV-004: Total Mismatch ($80.00 discrepancy: Subtotal $400 + Tax $40 = $440, Total is $520)
    doc_v01 = make_mock_doc(
        doc_type="invoice",
        vendor_name="Apex Lab Scientific Equipment Inc",
        invoice_id="APEX-2026-551",
        subtotal="400.00",
        tax="40.00",
        total="520.00",
        items=[
            ExtractedLineItem(item_index=0, description="Precision Scale", amount="250.00"),
            ExtractedLineItem(item_index=1, description="Probe Kit", amount="150.00"),
        ],
    )
    val_v01 = apply_all_validation_rules(doc_v01)
    assert val_v01.audit_status == "flagged"
    v01 = next((f for f in val_v01.validation_flags if f.rule_id == "V01"), None)
    assert v01 is not None
    assert v01.severity == "CRITICAL"
    assert "$80.00" in v01.reason
    assert v01.expected_value == "$440.00"
    assert v01.actual_value == "$520.00"

    # 2. INV-005: Missing Tax Number on Invoice
    doc_v02 = make_mock_doc(
        doc_type="invoice",
        vendor_name="Global Tech Summit Foundation",
        tax_id=None,
        invoice_id="GTSF-2026-302",
        subtotal="200.00",
        tax="0.00",
        total="200.00",
        items=[ExtractedLineItem(item_index=0, description="Pass", amount="200.00")],
    )
    val_v02 = apply_all_validation_rules(doc_v02)
    assert val_v02.audit_status == "flagged"
    v02 = next((f for f in val_v02.validation_flags if f.rule_id == "V02"), None)
    assert v02 is not None
    assert v02.severity == "MEDIUM"
    assert v02.field_name == "vendor_tax_id"

    # 3. INV-006: Outside Academic Term (May 15, 2026 is prior to Aug 1, 2026)
    doc_v04 = make_mock_doc(
        doc_type="invoice",
        vendor_name="CloudSim Simulation Systems",
        invoice_id="CSS-2026-119",
        invoice_date="2026-05-15",
        subtotal="95.00",
        tax="5.00",
        total="100.00",
        items=[ExtractedLineItem(item_index=0, description="License", amount="95.00")],
    )
    val_v04 = apply_all_validation_rules(doc_v04)
    assert val_v04.audit_status == "flagged"
    v04 = next((f for f in val_v04.validation_flags if f.rule_id == "V04"), None)
    assert v04 is not None
    assert v04.severity == "MEDIUM"
    assert "2026-05-15" in v04.actual_value


# ============================================================================
# TEST SUITE A3: Duplicate Detection (Exact File & Business Identifier)
# ============================================================================
def test_a3_duplicate_detection_and_low_confidence():
    """Verify exact file duplicate, business duplicate, and low-confidence highlighting."""
    # 1. Exact File Duplicate (Tier 1: matching SHA-256 hash across any document type)
    hashes = {"hash_invoice_001_sha256": "original_invoice_1.pdf"}
    b_keys = {}
    doc_exact = make_mock_doc(file_hash="hash_invoice_001_sha256")
    val_exact = apply_all_validation_rules(doc_exact, existing_hashes=hashes, existing_business_keys=b_keys)
    v03_exact = next((f for f in val_exact.validation_flags if f.rule_id == "V03"), None)
    assert v03_exact is not None
    assert v03_exact.rule_name == "Duplicate Document (Exact File)"
    assert v03_exact.severity == "CRITICAL"
    assert doc_exact.is_exact_duplicate is True
    assert "original_invoice_1.pdf" in v03_exact.reason

    # 2. Business Duplicate (Tier 2: different hash, matching normalized vendor + invoice number)
    b_keys_populated = {("apex labs", "INV001"): "prior_upload.pdf"}
    doc_business = make_mock_doc(
        file_hash="hash_completely_different_bytes",
        vendor_name="  Apex Labs, Inc.  ",
        invoice_id="  #INV-001  ",
    )
    val_business = apply_all_validation_rules(doc_business, existing_hashes={}, existing_business_keys=b_keys_populated)
    v03_biz = next((f for f in val_business.validation_flags if f.rule_id == "V03"), None)
    assert v03_biz is not None
    assert v03_biz.rule_name == "Duplicate Invoice (Business Identifier)"
    assert v03_biz.severity == "CRITICAL"
    assert doc_business.is_business_duplicate is True
    assert "prior_upload.pdf" in v03_biz.reason

    # 3. Receipt Duplicate Heuristic: merchant, date, total match is a WARNING heuristic, not definitive proof
    r_keys_populated = {("campus store", "2026-10-05", "216.00"): "prior_receipt.pdf"}
    doc_rec = make_mock_doc(
        doc_type="receipt",
        vendor_name="Campus Store LLC",
        invoice_date="2026-10-05",
        total="216.00",
        file_hash="hash_new_receipt_bytes",
    )
    val_rec = apply_all_validation_rules(
        doc_rec,
        existing_hashes={},
        existing_business_keys={},
        existing_receipt_keys=r_keys_populated,
    )
    v03_rec = next((f for f in val_rec.validation_flags if f.rule_id == "V03"), None)
    assert v03_rec is not None
    assert v03_rec.rule_name == "Potential Duplicate Receipt (Heuristic Match)"
    assert v03_rec.severity == "WARNING"
    # Receipt heuristic must NOT mark document as definitive duplicate
    assert val_rec.is_duplicate is False
    assert val_rec.is_business_duplicate is False


def test_v02_and_v05_responsibilities():
    """Verify distinct responsibilities for V02 (missing tax ID) and V05 (low confidence on extracted fields)."""
    # Case 1: Missing Tax ID on Invoice -> Triggers V02, does NOT trigger V05
    doc_missing_tax = make_mock_doc(
        doc_type="invoice",
        tax_id=None,
        confidence=0.95,
    )
    doc_missing_tax.vendor_tax_id.status = FieldStatus.MISSING
    doc_missing_tax.vendor_tax_id.confidence = None
    val_missing = apply_all_validation_rules(doc_missing_tax)
    v02 = next((f for f in val_missing.validation_flags if f.rule_id == "V02"), None)
    v05_tax = next((f for f in val_missing.validation_flags if f.rule_id == "V05" and f.field_name == "vendor_tax_id"), None)
    assert v02 is not None
    assert v02.severity == "MEDIUM"
    assert v05_tax is None  # A missing tax ID must NEVER generate a second low-confidence warning!

    # Case 2: Not-Applicable Tax ID on Receipt -> Triggers neither V02 nor V05
    doc_rec_tax = make_mock_doc(
        doc_type="receipt",
        tax_id=None,
        confidence=0.95,
    )
    val_rec = apply_all_validation_rules(doc_rec_tax)
    assert not any(f.rule_id == "V02" for f in val_rec.validation_flags)
    assert not any(f.rule_id == "V05" and f.field_name == "vendor_tax_id" for f in val_rec.validation_flags)

    # Case 3: Successfully Extracted with High Confidence (0.95 >= 0.85) -> No V05
    doc_high_conf = make_mock_doc(confidence=0.95)
    val_high = apply_all_validation_rules(doc_high_conf)
    assert not any(f.rule_id == "V05" for f in val_high.validation_flags)

    # Case 4: Successfully Extracted with Low Confidence (0.70 < 0.85) -> Triggers V05, not V02
    doc_low_conf = make_mock_doc(tax_id="66-4040004", confidence=0.95)
    doc_low_conf.vendor_tax_id.confidence = 0.70
    doc_low_conf.vendor_tax_id.status = FieldStatus.EXTRACTED
    val_low = apply_all_validation_rules(doc_low_conf)
    v02_low = next((f for f in val_low.validation_flags if f.rule_id == "V02"), None)
    v05_low = next((f for f in val_low.validation_flags if f.rule_id == "V05" and f.field_name == "vendor_tax_id"), None)
    assert v02_low is None  # Tax ID was extracted, so V02 does not flag
    assert v05_low is not None  # Low confidence triggered V05
    assert v05_low.severity == "WARNING"
    assert "70.0%" in v05_low.reason


def test_invoice_a3_exact_duplicate_end_to_end_via_api():
    """A3 Acceptance: Ingest an invoice twice via API, verify exact duplicate detection, original identification, and summary metrics."""
    invoice_path = (SAMPLES_DIR / "INV-001.pdf") if (SAMPLES_DIR / "INV-001.pdf").exists() else (SAMPLES_DIR / "clean_tuition_invoice_1.pdf")
    if not invoice_path.exists():
        legacy_dir = SAMPLES_DIR.parent / "samples_usd_legacy"
        invoice_path = legacy_dir / "clean_tuition_invoice_1.pdf"
    assert invoice_path.exists()
    file_bytes = invoice_path.read_bytes()

    # 1. First upload: Brand new document
    res1 = client.post(
        "/api/audit/upload",
        files=[("files", ("tuition_first.pdf", file_bytes, "application/pdf"))],
    )
    assert res1.status_code == 200
    data1 = res1.json()
    assert data1["successful_extractions"] == 1
    doc1 = data1["documents"][0]
    doc1_id = doc1["id"]
    assert doc1["is_duplicate"] is False
    assert doc1["is_exact_duplicate"] is False

    # 2. Second upload: Exact same file bytes
    res2 = client.post(
        "/api/audit/upload",
        files=[("files", ("tuition_reupload.pdf", file_bytes, "application/pdf"))],
    )
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["duplicate_files"] == 1
    assert len(data2["duplicates"]) == 1
    dup2 = data2["duplicates"][0]

    # 3. Confirm identified as exact-file duplicate with structured response
    assert dup2["is_duplicate"] is True
    assert dup2["is_exact_duplicate"] is True
    assert dup2["duplicate_type"] == "exact"
    assert dup2["existing_document_id"] == doc1_id
    assert "Exact duplicate document detected" in dup2["message"]

    # 4. Confirm original document is identifiable
    assert dup2["existing_file_name"] == "tuition_first.pdf"

    # 5. Confirm no second document record was created in SQLite
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT count(*) as cnt FROM documents;")
        total_docs = cursor.fetchone()["cnt"]
        assert total_docs == 1, "Level 1 duplicate must NOT create a new document record in SQLite"

    # 6. Confirm original document is unchanged and visible through single document API
    get_res = client.get(f"/api/audit/documents/{doc1_id}")
    assert get_res.status_code == 200
    retrieved = get_res.json()
    assert retrieved["id"] == doc1_id


def test_vendor_normalization_false_positive_prevention():
    """Verify vendor normalization preserves distinct entities and avoids false positives on similar base names."""
    # Vendors with similar base names but distinct identities
    v1 = "Apex Labs"
    v2 = "Apex Health"
    v3 = "Apex Technologies"
    v4 = "Apex Labs, Inc."

    from app.db.repository import normalize_vendor_name, normalize_business_key

    n1 = normalize_vendor_name(v1)
    n2 = normalize_vendor_name(v2)
    n3 = normalize_vendor_name(v3)
    n4 = normalize_vendor_name(v4)

    assert n1 == "apex labs"
    assert n2 == "apex health"
    assert n3 == "apex technologies"
    assert n4 == "apex labs"  # Trailing corporate designation stripped

    # Distinct vendors with same invoice number must NOT match
    b_key_v1 = normalize_business_key(v1, "INV-100")
    b_key_v2 = normalize_business_key(v2, "INV-100")
    b_key_v3 = normalize_business_key(v3, "INV-100")
    b_key_v4 = normalize_business_key(v4, "INV-100")

    assert b_key_v1 != b_key_v2
    assert b_key_v1 != b_key_v3
    assert b_key_v1 == b_key_v4  # Apex Labs matches Apex Labs, Inc.

    # Corporate designation as root word at start of name must NOT be stripped
    assert normalize_vendor_name("Inc Magazine") == "inc magazine"
    assert normalize_vendor_name("LTD Commodities") == "ltd commodities"


# ============================================================================
# Additional Comprehensive Validation Tests
# ============================================================================
def test_financial_calculations_tax_inclusive_and_discounts():
    """Verify tax-inclusive receipts, tax-exclusive reconciliations, discounts, adjustments, and tolerance."""
    # 1. Tax-exclusive: line sum ($100) + tax ($10) = total ($110)
    doc_excl = make_mock_doc(
        subtotal="100.00",
        tax="10.00",
        total="110.00",
        items=[ExtractedLineItem(item_index=0, description="Item", amount="100.00")],
    )
    assert validate_v01_total_mismatch(doc_excl) is None

    # 2. Tax-inclusive: line item $100.00 directly matches Total $100.00 with tax $10 broken out
    doc_incl = make_mock_doc(
        subtotal="100.00",
        tax="10.00",
        total="100.00",
        items=[ExtractedLineItem(item_index=0, description="Gross item", amount="100.00")],
    )
    assert validate_v01_total_mismatch(doc_incl) is None

    # 3. Discounts: Subtotal $100.00 - Discount $15.00 + Tax $8.50 = Total $93.50
    doc_disc = make_mock_doc(
        subtotal="100.00",
        tax="8.50",
        total="93.50",
        items=[ExtractedLineItem(item_index=0, description="Item", amount="100.00")],
    )
    doc_disc.discounts = ExtractedField(value="15.00", confidence=0.95)
    assert validate_v01_total_mismatch(doc_disc) is None

    # 4. Adjustments: Subtotal $100.00 + Adjustment $10.00 + Tax $11.00 = Total $121.00
    doc_adj = make_mock_doc(
        subtotal="100.00",
        tax="11.00",
        total="121.00",
        items=[ExtractedLineItem(item_index=0, description="Item", amount="100.00")],
    )
    doc_adj.adjustments = ExtractedField(value="10.00", confidence=0.95)
    assert validate_v01_total_mismatch(doc_adj) is None

    # 5. Currency rounding tolerance: diff of $0.01 is within $0.02 tolerance -> PASS
    doc_cent_diff = make_mock_doc(
        subtotal="100.00",
        tax="10.00",
        total="110.01",
        items=[ExtractedLineItem(item_index=0, description="Item", amount="100.00")],
    )
    assert validate_v01_total_mismatch(doc_cent_diff) is None

    # 6. Diff of $0.05 exceeds $0.02 tolerance -> FLAGGED
    doc_cent_exceed = make_mock_doc(
        subtotal="100.00",
        tax="10.00",
        total="110.05",
        items=[ExtractedLineItem(item_index=0, description="Item", amount="100.00")],
    )
    assert validate_v01_total_mismatch(doc_cent_exceed) is not None


def test_partial_line_item_extraction_triggers_manual_review():
    """When a line item has missing or unparsable amount, V01 flags Partial Line-Item Extraction (HIGH)."""
    doc_partial = make_mock_doc(
        subtotal="100.00",
        tax="10.00",
        total="110.00",
        items=[
            ExtractedLineItem(item_index=0, description="Complete Item", amount="100.00"),
            ExtractedLineItem(item_index=1, description="Partial Item with No Amount", amount=None),
        ],
    )
    flag = validate_v01_total_mismatch(doc_partial)
    assert flag is not None
    assert flag.rule_id == "V01"
    assert flag.rule_name == "Partial Line-Item Extraction"
    assert flag.severity == "HIGH"
    assert "manual audit review" in flag.reason.lower()


def test_audit_status_precedence_and_multi_flag():
    """Verify precedence: CRITICAL violation is never hidden by pending review or lower-severity flags."""
    doc_multi = make_mock_doc(
        subtotal="400.00",
        tax="40.00",
        total="520.00",  # V01 CRITICAL Total Mismatch ($80 discrepancy)
        tax_id=None,     # V02 MEDIUM Missing Tax ID
        items=[ExtractedLineItem(item_index=0, description="Item A", amount="400.00", confidence=0.95)],
        confidence=0.95,
    )
    doc_multi.vendor_tax_id.status = FieldStatus.MISSING
    doc_multi.invoice_id.confidence = 0.70  # V05 WARNING Low Confidence

    validated = apply_all_validation_rules(doc_multi)

    # 1. Must contain all 3 flags
    rule_ids = [f.rule_id for f in validated.validation_flags]
    assert "V01" in rule_ids
    assert "V02" in rule_ids
    assert "V05" in rule_ids

    # 2. Highest severity is CRITICAL
    assert validated.highest_severity == "CRITICAL"

    # 3. Overall audit_status is flagged
    assert validated.audit_status == "flagged"

    # 4. Pending manual review does NOT silence or hide the critical flag
    assert validated.manual_review_status == "pending"

    # 5. When auditor reviews and approves override
    doc_id = save_document(validated)
    update_manual_review(doc_id, status="approved", notes="Auditor verified $80 discrepancy authorized.")
    retrieved = get_document_by_id(doc_id)

    assert retrieved.audit_status == "reviewed"
    assert retrieved.manual_review_status == "approved"
    assert retrieved.highest_severity == "CRITICAL"
    # All flags remain fully preserved and queryable
    assert len(retrieved.validation_flags) >= 3


def test_ambiguous_calculation_requires_manual_review():
    """When line items do not sum to subtotal or total, rule V01 flags MANUAL_REVIEW_REQUIRED."""
    # Line items = $80.00, Subtotal = $100.00, Tax = $10.00, Total = $110.00 (Line items don't reconcile)
    doc_ambiguous = make_mock_doc(
        subtotal="100.00",
        tax="10.00",
        total="110.00",
        items=[ExtractedLineItem(item_index=0, description="Item partial", amount="80.00")],
    )
    flag = validate_v01_total_mismatch(doc_ambiguous)
    assert flag is not None
    assert flag.rule_id == "V01"
    assert flag.severity == "HIGH"
    assert "manual audit review" in flag.reason.lower()


def test_date_validation_missing_and_unparsable():
    """Missing or unparsable date triggers HIGH severity manual review."""
    # Missing date
    doc_none_date = make_mock_doc(invoice_date=None)
    flag_none = validate_v04_outside_academic_term(doc_none_date)
    assert flag_none is not None
    assert flag_none.severity == "HIGH"

    # Unparsable date
    doc_bad_date = make_mock_doc(invoice_date="InvalidCalendarDate123")
    flag_bad = validate_v04_outside_academic_term(doc_bad_date)
    assert flag_bad is not None
    assert flag_bad.severity == "HIGH"

    # Inclusive boundary: exactly on start boundary 2026-08-01 -> PASS
    doc_start_bound = make_mock_doc(invoice_date="2026-08-01")
    assert validate_v04_outside_academic_term(doc_start_bound) is None

    # Inclusive boundary: exactly on end boundary 2026-12-31 -> PASS
    doc_end_bound = make_mock_doc(invoice_date="2026-12-31")
    assert validate_v04_outside_academic_term(doc_end_bound) is None


# ============================================================================
# Audit Orchestrator: Idempotency & Manual Review Retention
# ============================================================================
def test_audit_orchestrator_revalidation_idempotency():
    """Verify that re-running validation does not duplicate records/flags and preserves reviewer notes."""
    doc = make_mock_doc(subtotal="100.00", tax="10.00", total="125.00")  # Triggers V01 mismatch
    validated = apply_all_validation_rules(doc)
    doc_id = save_document(validated)

    # Auditor adds notes
    update_manual_review(doc_id, status="approved", notes="Override approved: Discrepancy verified with supplier.")

    # Re-run validation via orchestrator
    revalidated = orchestrator.revalidate_document(doc_id)
    assert revalidated is not None
    assert revalidated.id == doc_id
    assert revalidated.manual_review_status == "approved"
    assert "Discrepancy verified with supplier" in revalidated.manual_review_notes

    # Verify no duplicate flags created in database
    retrieved = get_document_by_id(doc_id)
    v01_count = len([f for f in retrieved.validation_flags if f.rule_id == "V01"])
    assert v01_count == 1
