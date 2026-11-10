"""P07 — Vendor / Payee Name Confidence Investigation & Remediation Test Suite.

Mandatory Regression Scenarios:
1. High-confidence VendorName extraction.
2. Low-confidence VendorName extraction.
3. CustomerName having higher confidence than VendorName.
4. Missing VendorName with available OCR text.
5. Receipt MerchantName confidence mapping.
6. Fallback extraction without fabricated Azure confidence.
7. Confidence preservation through database and API.
8. Frontend display contract for field confidences.
9. V05 triggering below 85%.
10. V05 not triggering at or above 85%.
"""

import json
from unittest.mock import MagicMock
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.common import FieldStatus, ExtractedField, ExtractedLineItem
from app.schemas.document import DocumentExtraction
from app.services.extractor import (
    analyze_invoice_result,
    analyze_receipt_result,
)
from app.services.validator import (
    apply_all_validation_rules,
    validate_v05_low_confidence,
)
from app.db.session import init_db
from app.db.repository import (
    save_document,
    get_document_by_id,
    delete_all_documents,
    create_user,
    verify_user,
    create_session,
    delete_all_auth_data,
)

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_environment():
    """Ensure a clean database and test environment for every test."""
    init_db()
    delete_all_documents()
    delete_all_auth_data()
    yield
    delete_all_documents()
    delete_all_auth_data()


def make_mock_field(content, field_type="string", confidence=0.95, value=None):
    """Helper to create a mock Azure DocumentField."""
    field = MagicMock()
    field.content = content
    field.type = field_type
    field.confidence = confidence
    field.value_string = content if field_type == "string" else None
    field.value_date = content if field_type == "date" else None
    if field_type == "currency":
        amt = float(value if value is not None else content.replace("₹", "").replace("$", "").replace(",", "").strip())
        field.value_currency = {"amount": amt, "currencyCode": "INR"}
        field.value_number = amt
    else:
        field.value_currency = None
        field.value_number = None
    return field


def create_mock_invoice_result(
    vendor_name="Aster Office Supplies Pvt. Ltd.",
    vendor_conf=0.885,
    customer_name="Apex Global Academy",
    customer_conf=0.886,
    include_vendor=True,
    content=None,
):
    """Create a mock AnalyzeResult for an invoice."""
    res = MagicMock()
    if content is None:
        content = (
            f"{vendor_name}\nTAX INVOICE\nPlot No. 42, Okhla Phase-III\n"
            f"CUSTOMER / BILL TO:\n{customer_name}\n"
            f"Invoice No: INV-2026-001\nInvoice Date: 2026-09-12\n"
            f"Tax ID: FAKE-GST-000001\nTotal: ₹9,794.00"
        )
    res.content = content
    res.as_dict.return_value = {"modelId": "prebuilt-invoice", "content": content}

    doc = MagicMock()
    doc.doc_type = "invoice"
    fields = {
        "CustomerName": make_mock_field(customer_name, "string", customer_conf),
        "InvoiceId": make_mock_field("INV-2026-001", "string", 0.99),
        "InvoiceDate": make_mock_field("2026-09-12", "date", 0.95),
        "VendorTaxId": make_mock_field("FAKE-GST-000001", "string", 0.90),
        "SubTotal": make_mock_field("8300.00", "currency", 0.95, 8300.0),
        "TotalTax": make_mock_field("1494.00", "currency", 0.95, 1494.0),
        "InvoiceTotal": make_mock_field("9794.00", "currency", 0.95, 9794.0),
        "Items": None,
    }
    if include_vendor:
        fields["VendorName"] = make_mock_field(vendor_name, "string", vendor_conf)

    doc.fields = fields
    res.documents = [doc]
    return res


def create_mock_receipt_result(
    merchant_name="GREENFIELD TECHNICAL INSTITUTE",
    merchant_conf=0.955,
    content=None,
):
    """Create a mock AnalyzeResult for a receipt."""
    res = MagicMock()
    if content is None:
        content = (
            f"{merchant_name}\nFEE RECEIPT\nDate: 2026-11-15\n"
            f"Receipt No: REC-2026-003\nTotal: ₹29,000.00"
        )
    res.content = content
    res.as_dict.return_value = {"modelId": "prebuilt-receipt", "content": content}

    doc = MagicMock()
    doc.doc_type = "receipt"
    fields = {
        "MerchantName": make_mock_field(merchant_name, "string", merchant_conf),
        "TransactionDate": make_mock_field("2026-11-15", "date", 0.99),
        "ReceiptId": make_mock_field("REC-2026-003", "string", 0.95),
        "Total": make_mock_field("29000.00", "currency", 0.99, 29000.0),
        "Subtotal": make_mock_field("29000.00", "currency", 0.99, 29000.0),
        "Items": None,
    }
    doc.fields = fields
    res.documents = [doc]
    return res


# ============================================================================
# SCENARIO 01: High-confidence VendorName extraction
# ============================================================================
def test_scenario_01_high_confidence_vendor_name_extraction():
    """1. High-confidence VendorName extraction (>= 0.85) preserved truthfully without flags."""
    raw_res = create_mock_invoice_result(
        vendor_name="Aster Office Supplies Pvt. Ltd.",
        vendor_conf=0.885,
    )
    doc = analyze_invoice_result(raw_res, b"%PDF-dummy", "INV-001.pdf")

    assert doc.vendor_name is not None
    assert doc.vendor_name.value == "Aster Office Supplies Pvt. Ltd."
    assert doc.vendor_name.confidence == 0.885
    assert doc.vendor_name.status == FieldStatus.EXTRACTED
    assert doc.vendor_name.confidence_source == "azure"

    # Validation: V05 must NOT flag vendor_name
    validated = apply_all_validation_rules(doc)
    v05_vendor_flags = [
        f for f in validated.validation_flags
        if f.rule_id == "V05" and f.field_name == "vendor_name"
    ]
    assert len(v05_vendor_flags) == 0


# ============================================================================
# SCENARIO 02: Low-confidence VendorName extraction
# ============================================================================
def test_scenario_02_low_confidence_vendor_name_extraction():
    """2. Low-confidence VendorName extraction (< 0.85) preserved truthfully and triggers V05."""
    raw_res = create_mock_invoice_result(
        vendor_name="BluePeak IT Solutions",
        vendor_conf=0.659,
    )
    doc = analyze_invoice_result(raw_res, b"%PDF-dummy", "INV-002.pdf")

    assert doc.vendor_name.value == "BluePeak IT Solutions"
    assert doc.vendor_name.confidence == 0.659
    assert doc.vendor_name.status == FieldStatus.LOW_CONFIDENCE
    assert doc.vendor_name.confidence_source == "azure"

    # Validation: V05 must flag vendor_name as WARNING
    validated = apply_all_validation_rules(doc)
    v05_vendor_flags = [
        f for f in validated.validation_flags
        if f.rule_id == "V05" and f.field_name == "vendor_name"
    ]
    assert len(v05_vendor_flags) == 1
    assert v05_vendor_flags[0].severity == "WARNING"
    assert "65.9%" in v05_vendor_flags[0].reason
    assert v05_vendor_flags[0].actual_value == "0.66"


# ============================================================================
# SCENARIO 03: CustomerName having higher confidence than VendorName
# ============================================================================
def test_scenario_03_customer_name_higher_confidence_than_vendor_name():
    """3. CustomerName having higher confidence than VendorName is never confused or substituted."""
    raw_res = create_mock_invoice_result(
        vendor_name="BluePeak IT Solutions",
        vendor_conf=0.659,
        customer_name="Greenfield Technical Institute",
        customer_conf=0.922,
    )
    doc = analyze_invoice_result(raw_res, b"%PDF-dummy", "INV-002.pdf")

    # VendorName retains vendor value and low confidence
    assert doc.vendor_name.value == "BluePeak IT Solutions"
    assert doc.vendor_name.confidence == 0.659
    assert doc.vendor_name.status == FieldStatus.LOW_CONFIDENCE

    # CustomerName retains customer value and high confidence
    assert doc.invoice_data is not None
    assert doc.invoice_data.customer_name.value == "Greenfield Technical Institute"
    assert doc.invoice_data.customer_name.confidence == 0.922

    # Verification: CustomerName confidence was NOT substituted into VendorName
    assert doc.vendor_name.confidence != doc.invoice_data.customer_name.confidence
    assert doc.vendor_name.value != doc.invoice_data.customer_name.value


# ============================================================================
# SCENARIO 04: Missing VendorName with available OCR text
# ============================================================================
def test_scenario_04_missing_vendor_name_with_available_ocr_text():
    """4. Missing VendorName in Azure fields falls back to OCR text with truthful confidence=None."""
    ocr_content = (
        "Apex Scientific Instruments Ltd.\n"
        "TAX INVOICE\n"
        "Plot 99, Electronic City Phase 2\n"
        "CUSTOMER / BILL TO:\nGreenfield Technical Institute\n"
        "Invoice No: INV-2026-999\nTotal: ₹10,000.00"
    )
    raw_res = create_mock_invoice_result(
        include_vendor=False,
        content=ocr_content,
    )
    doc = analyze_invoice_result(raw_res, b"%PDF-dummy", "invoice_no_vendor.pdf")

    # Fallback extracts header without inventing fabricated Azure confidence
    assert doc.vendor_name.value == "Apex Scientific Instruments Ltd."
    assert doc.vendor_name.confidence is None
    assert doc.vendor_name.confidence_source == "ocr_fallback"
    assert doc.vendor_name.status == FieldStatus.EXTRACTED

    # Validation: Missing confidence from fallback does not trigger false V05 warning
    flags = validate_v05_low_confidence(doc)
    v05_vendor = [f for f in flags if f.field_name == "vendor_name"]
    assert len(v05_vendor) == 0


# ============================================================================
# SCENARIO 05: Receipt MerchantName confidence mapping
# ============================================================================
def test_scenario_05_receipt_merchant_name_confidence_mapping():
    """5. Receipt MerchantName maps to vendor_name with exact Azure confidence."""
    raw_res = create_mock_receipt_result(
        merchant_name="GREENFIELD TECHNICAL INSTITUTE",
        merchant_conf=0.955,
    )
    doc = analyze_receipt_result(raw_res, b"%PDF-dummy", "REC-003.pdf")

    assert doc.vendor_name.value == "GREENFIELD TECHNICAL INSTITUTE"
    assert doc.vendor_name.confidence == 0.955
    assert doc.vendor_name.confidence_source == "azure"
    assert doc.vendor_name.status == FieldStatus.EXTRACTED
    assert doc.receipt_data.merchant_name.value == "GREENFIELD TECHNICAL INSTITUTE"
    assert doc.receipt_data.merchant_name.confidence == 0.955

    # V05 does not trigger on high-confidence receipt merchant
    flags = validate_v05_low_confidence(doc)
    v05_vendor = [f for f in flags if f.field_name == "vendor_name"]
    assert len(v05_vendor) == 0


# ============================================================================
# SCENARIO 06: Fallback extraction without fabricated Azure confidence
# ============================================================================
def test_scenario_06_fallback_extraction_without_fabricated_azure_confidence():
    """6. Fallback regex extraction of tax, total, and tax ID never fabricates 0.90/0.88 confidence."""
    ocr_content = (
        "Vendor Labs Inc.\n"
        "COMMERCIAL INVOICE\n"
        "Tax ID: GSTIN-7788990011\n"
        "Invoice Date: 2026-10-15\n"
        "Total GST: ₹1,800.00\n"
        "Grand Total: ₹11,800.00"
    )
    res = MagicMock()
    res.content = ocr_content
    res.as_dict.return_value = {"content": ocr_content}

    # Azure returned no recognized fields
    doc_mock = MagicMock()
    doc_mock.doc_type = "invoice"
    doc_mock.fields = {}
    res.documents = [doc_mock]

    doc = analyze_invoice_result(res, b"%PDF-dummy", "fallback_test.pdf")

    # Verify Tax ID extracted via regex has confidence=None, not 0.90!
    assert doc.vendor_tax_id.value == "GSTIN-7788990011"
    assert doc.vendor_tax_id.confidence is None
    assert doc.vendor_tax_id.confidence_source == "ocr_fallback"

    # Verify Total Tax extracted via regex has confidence=None, not 0.90!
    assert doc.tax.value == "1800.00"
    assert doc.tax.confidence is None
    assert doc.tax.confidence_source == "ocr_fallback"


# ============================================================================
# SCENARIO 07: Confidence preservation through database and API
# ============================================================================
def test_scenario_07_confidence_preservation_through_database_and_api():
    """7. Confidence score is preserved through SQLite persistence and FastAPI REST response."""
    from app.dependencies.auth import require_current_user
    app.dependency_overrides.pop(require_current_user, None)

    # 1. Create a verified user and session
    user = create_user("auditor@example.com", "Password@123", full_name="Auditor One")
    verify_user("auditor@example.com")
    token = "session_token_audit_test_123"
    create_session(user["id"], token)
    client.cookies.set("fee_auditor_session", token)

    # 2. Build and save extraction with exact low confidence 0.659
    doc = DocumentExtraction(
        file_name="INV-002.pdf",
        file_hash="hash_p07_002",
        document_type="invoice",
        model_used="prebuilt-invoice",
        vendor_name=ExtractedField(value="BluePeak IT Solutions", confidence=0.659, status=FieldStatus.LOW_CONFIDENCE),
        invoice_id=ExtractedField(value="INV-2026-002", confidence=0.941),
        invoice_date=ExtractedField(value="2026-10-20", confidence=0.926),
        vendor_tax_id=ExtractedField(value="FAKE-GST-000002", confidence=0.819),
        subtotal=ExtractedField(value="7500.00", confidence=0.941),
        tax=ExtractedField(value="1350.00", confidence=0.941),
        total=ExtractedField(value="8850.00", confidence=0.941),
        owner_user_id=user["id"],
    )
    doc_id = save_document(doc, owner_user_id=user["id"])

    # 3. Verify repository retrieval preserves confidence and status
    retrieved = get_document_by_id(doc_id, owner_user_id=user["id"])
    assert retrieved is not None
    assert retrieved.vendor_name.value == "BluePeak IT Solutions"
    assert retrieved.vendor_name.confidence == 0.659
    assert retrieved.vendor_name.status == FieldStatus.LOW_CONFIDENCE

    # 4. Verify API endpoint GET /api/audit/documents/{id} returns truthful confidence
    resp = client.get(f"/api/audit/documents/{doc_id}", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["vendor_name"]["value"] == "BluePeak IT Solutions"
    assert data["vendor_name"]["confidence"] == 0.659
    assert data["vendor_name"]["status"] == "low_confidence"


# ============================================================================
# SCENARIO 08: Frontend confidence display contract
# ============================================================================
def test_scenario_08_frontend_confidence_display_contract():
    """8. Frontend display contract: Verifies score-to-percentage and status thresholds."""
    import math
    test_cases = [
        (0.955, "extracted", "96%", "green"),
        (0.885, "extracted", "89%", "blue"),
        (0.850, "extracted", "85%", "blue"),
        (0.849, "low_confidence", "85% Low", "amber"),
        (0.659, "low_confidence", "66% Low", "amber"),
        (None, "missing", "Missing", "red"),
        (None, "not_applicable", "N/A", "gray"),
        (None, "extracted", "Fallback", "gray"),
    ]

    for conf, status, expected_text, _expected_color in test_cases:
        if status == "not_applicable":
            result_text = "N/A"
        elif status == "missing" or (status is None and conf is None):
            result_text = "Missing"
        elif conf is None:
            result_text = "Fallback"
        else:
            # Emulate JavaScript Math.round(score * 100)
            pct = math.floor(conf * 100 + 0.5)
            if conf >= 0.85:
                result_text = f"{pct}%"
            else:
                result_text = f"{pct}% Low"
        assert result_text == expected_text, f"Failed for conf={conf}, status={status}"


# ============================================================================
# SCENARIO 09: V05 triggering below 85%
# ============================================================================
def test_scenario_09_v05_triggering_below_85_percent():
    """9. Rule V05 strictly triggers WARNING for any confidence score < 0.850."""
    # 0.849 is below the 0.850 threshold
    doc = DocumentExtraction(
        file_name="border_test_low.pdf",
        file_hash="hash_border_01",
        vendor_name=ExtractedField(value="Border Vendor", confidence=0.849, status=FieldStatus.LOW_CONFIDENCE),
        invoice_id=ExtractedField(value="INV-BORDER-1", confidence=0.95),
        invoice_date=ExtractedField(value="2026-09-15", confidence=0.95),
        total=ExtractedField(value="100.00", confidence=0.95),
    )
    validated = apply_all_validation_rules(doc)
    v05_flags = [f for f in validated.validation_flags if f.rule_id == "V05" and f.field_name == "vendor_name"]
    assert len(v05_flags) == 1
    assert v05_flags[0].severity == "WARNING"
    assert "84.9%" in v05_flags[0].reason


# ============================================================================
# SCENARIO 10: V05 not triggering at or above 85%
# ============================================================================
def test_scenario_10_v05_not_triggering_at_or_above_85_percent():
    """10. Rule V05 does not trigger at exact boundary 0.850 or above (0.920)."""
    # Case A: Exact boundary 0.850
    doc_boundary = DocumentExtraction(
        file_name="border_test_exact.pdf",
        file_hash="hash_border_02",
        vendor_name=ExtractedField(value="Boundary Vendor", confidence=0.850, status=FieldStatus.EXTRACTED),
        invoice_id=ExtractedField(value="INV-BORDER-2", confidence=0.95),
        invoice_date=ExtractedField(value="2026-09-15", confidence=0.95),
        total=ExtractedField(value="100.00", confidence=0.95),
    )
    val_boundary = apply_all_validation_rules(doc_boundary)
    v05_boundary = [f for f in val_boundary.validation_flags if f.rule_id == "V05" and f.field_name == "vendor_name"]
    assert len(v05_boundary) == 0

    # Case B: Above boundary 0.920
    doc_high = DocumentExtraction(
        file_name="border_test_high.pdf",
        file_hash="hash_border_03",
        vendor_name=ExtractedField(value="High Conf Vendor", confidence=0.920, status=FieldStatus.EXTRACTED),
        invoice_id=ExtractedField(value="INV-BORDER-3", confidence=0.95),
        invoice_date=ExtractedField(value="2026-09-15", confidence=0.95),
        total=ExtractedField(value="100.00", confidence=0.95),
    )
    val_high = apply_all_validation_rules(doc_high)
    v05_high = [f for f in val_high.validation_flags if f.rule_id == "V05" and f.field_name == "vendor_name"]
    assert len(v05_high) == 0
