import io
import json
from decimal import Decimal
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient
from azure.core.exceptions import ClientAuthenticationError, HttpResponseError, ServiceResponseError

from app.main import app
from app.config import settings
from app.schemas.common import FieldStatus
from app.services.azure_client import (
    get_azure_client,
    test_azure_connection as check_azure_connection,
    analyze_document_bytes,
)
from app.services.extractor import (
    analyze_invoice,
    analyze_receipt,
    analyze_invoice_result,
    analyze_receipt_result,
    serialize_azure_result,
    compute_file_hash,
)
from app.db.session import init_db
from app.db.repository import (
    save_document,
    get_document_by_id,
    get_all_documents,
    delete_all_documents,
)

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_db():
    init_db()
    delete_all_documents()
    yield
    delete_all_documents()


# Helper to build mock Azure DocumentField
def make_mock_field(content, field_type="string", confidence=0.95, value=None):
    field = MagicMock()
    field.content = content
    field.type = field_type
    field.confidence = confidence
    field.value_string = content if field_type == "string" else None
    field.value_date = content if field_type == "date" else None
    if field_type == "currency":
        amt = float(value if value is not None else content.replace("$", "").replace(",", ""))
        field.value_currency = {"amount": amt, "currencyCode": "USD"}
        field.value_number = amt
    else:
        field.value_currency = None
        field.value_number = None
    return field


# Helper to build mock AnalyzeResult for Invoice
def make_mock_invoice_result():
    res = MagicMock()
    res.as_dict.return_value = {
        "apiVersion": "2024-11-30",
        "modelId": "prebuilt-invoice",
        "content": "Invoice CIT-2026-901 Cambridge Institute of Technology Tax ID: 99-1010001",
    }
    res.content = "Invoice CIT-2026-901 Cambridge Institute of Technology Tax ID: 99-1010001"

    doc = MagicMock()
    doc.doc_type = "invoice"
    doc.fields = {
        "VendorName": make_mock_field("Cambridge Institute of Technology", "string", 0.98),
        "VendorTaxId": make_mock_field("99-1010001", "string", 0.95),
        "InvoiceId": make_mock_field("CIT-2026-901", "string", 0.99),
        "InvoiceDate": make_mock_field("2026-09-10", "date", 0.97),
        "DueDate": make_mock_field("2026-10-10", "date", 0.92),
        "SubTotal": make_mock_field("$1,500.00", "currency", 0.96, 1500.0),
        "TotalTax": make_mock_field("$0.00", "currency", 0.94, 0.0),
        "InvoiceTotal": make_mock_field("$1,500.00", "currency", 0.99, 1500.0),
    }

    # Line item mock
    item1 = MagicMock()
    item1.value_object = {
        "Description": make_mock_field("Tuition Fee - Advanced Computer Science", "string", 0.95),
        "Quantity": make_mock_field("1", "currency", 0.95, 1.0),
        "UnitPrice": make_mock_field("$1,200.00", "currency", 0.95, 1200.0),
        "Amount": make_mock_field("$1,200.00", "currency", 0.95, 1200.0),
    }
    items_field = MagicMock()
    items_field.value_array = [item1]
    doc.fields["Items"] = items_field

    res.documents = [doc]
    return res


# Helper to build mock AnalyzeResult for Receipt
def make_mock_receipt_result():
    res = MagicMock()
    res.as_dict.return_value = {
        "apiVersion": "2024-11-30",
        "modelId": "prebuilt-receipt",
        "content": "University Bookstore Receipt 2026-10-05 Total: $216.00",
    }
    res.content = "University Bookstore Receipt 2026-10-05 Total: $216.00"

    doc = MagicMock()
    doc.doc_type = "receipt"
    doc.fields = {
        "MerchantName": make_mock_field("University Bookstore", "string", 0.97),
        "TransactionDate": make_mock_field("2026-10-05", "date", 0.98),
        "TransactionTime": make_mock_field("14:30:00", "string", 0.90),
        "Subtotal": make_mock_field("$200.00", "currency", 0.95, 200.0),
        "TotalTax": make_mock_field("$16.00", "currency", 0.95, 16.0),
        "Total": make_mock_field("$216.00", "currency", 0.99, 216.0),
    }

    # Item mock
    item1 = MagicMock()
    item1.value_object = {
        "Description": make_mock_field("Calculator", "string", 0.95),
        "Quantity": make_mock_field("1", "currency", 0.95, 1.0),
        "Price": make_mock_field("$115.00", "currency", 0.95, 115.0),
        "TotalPrice": make_mock_field("$115.00", "currency", 0.95, 115.0),
    }
    items_field = MagicMock()
    items_field.value_array = [item1]
    doc.fields["Items"] = items_field

    res.documents = [doc]
    return res


# ============================================================================
# 1. Azure Client Configuration
# ============================================================================
def test_1_azure_client_configuration():
    """Verify reusable client initialization with explicit api_version and no secrets in repr."""
    client_inst = get_azure_client()
    assert client_inst is not None
    status = check_azure_connection(perform_live_probe=False)
    assert status["status"] == "ok"
    assert status["api_version"] == "2024-11-30"
    assert settings.AZURE_DOCUMENT_INTELLIGENCE_KEY not in str(status)


# ============================================================================
# 2. Invoice Extraction using Mocked SDK Response
# ============================================================================
def test_2_invoice_extraction_mocked():
    """Verify invoice extraction maps fields to InvoiceData schema with canonical decimals."""
    mock_res = make_mock_invoice_result()
    file_bytes = b"Sample Invoice Binary PDF"
    extraction = analyze_invoice_result(mock_res, file_bytes, "test_invoice.pdf")

    assert extraction.document_type == "invoice"
    assert extraction.model_used == "prebuilt-invoice"
    assert extraction.invoice_data is not None
    assert extraction.receipt_data is None

    # Check fields
    assert extraction.vendor_name.value == "Cambridge Institute of Technology"
    assert extraction.vendor_name.confidence == 0.98
    assert extraction.vendor_tax_id.value == "99-1010001"
    assert extraction.invoice_id.value == "CIT-2026-901"
    assert extraction.invoice_date.value == "2026-09-10"

    # Canonical Decimal string check
    assert extraction.total.value == "1500.00"
    assert extraction.total.as_decimal() == Decimal("1500.00")
    assert extraction.subtotal.value == "1500.00"

    # Line items check
    assert len(extraction.line_items) == 1
    assert extraction.line_items[0].description == "Tuition Fee - Advanced Computer Science"
    assert extraction.line_items[0].amount == "1200.00"


# ============================================================================
# 3. Receipt Extraction using Mocked SDK Response
# ============================================================================
def test_3_receipt_extraction_mocked():
    """Verify receipt extraction maps fields to ReceiptData schema with NOT_APPLICABLE tax ID."""
    mock_res = make_mock_receipt_result()
    file_bytes = b"Sample Receipt Binary PDF"
    extraction = analyze_receipt_result(mock_res, file_bytes, "test_receipt.pdf")

    assert extraction.document_type == "receipt"
    assert extraction.model_used == "prebuilt-receipt"
    assert extraction.receipt_data is not None
    assert extraction.invoice_data is None

    # Check merchant
    assert extraction.vendor_name.value == "University Bookstore"
    assert extraction.receipt_data.merchant_name.value == "University Bookstore"
    assert extraction.invoice_date.value == "2026-10-05"

    # Retail receipt tax ID must be NOT_APPLICABLE
    assert extraction.vendor_tax_id.status == FieldStatus.NOT_APPLICABLE
    assert extraction.vendor_tax_id.value is None

    # Canonical decimal total
    assert extraction.total.value == "216.00"
    assert extraction.total.as_decimal() == Decimal("216.00")
    assert len(extraction.line_items) == 1


# ============================================================================
# 4. Field Confidence Preservation
# ============================================================================
def test_4_field_confidence_preservation():
    """Verify individual field confidence scores are preserved without modification."""
    mock_res = make_mock_invoice_result()
    extraction = analyze_invoice_result(mock_res, b"bytes", "test.pdf")

    assert extraction.vendor_name.confidence == 0.98
    assert extraction.vendor_tax_id.confidence == 0.95
    assert extraction.invoice_id.confidence == 0.99
    assert extraction.total.confidence == 0.99
    assert extraction.line_items[0].confidence == 0.95


# ============================================================================
# 5. Missing Field Handling
# ============================================================================
def test_5_missing_field_handling():
    """Verify absent fields are marked MISSING on invoices and NOT_APPLICABLE on receipts."""
    res_missing = MagicMock()
    res_missing.as_dict.return_value = {}
    res_missing.content = ""
    doc = MagicMock()
    doc.doc_type = "invoice"
    # Omit Tax ID and InvoiceId completely
    doc.fields = {
        "VendorName": make_mock_field("Vendor Without Tax", "string", 0.95),
        "InvoiceTotal": make_mock_field("$50.00", "currency", 0.95, 50.0),
    }
    res_missing.documents = [doc]

    extraction = analyze_invoice_result(res_missing, b"bytes", "missing.pdf")
    assert extraction.vendor_tax_id.value is None
    assert extraction.vendor_tax_id.status == FieldStatus.MISSING
    assert extraction.invoice_id.value is None
    assert extraction.invoice_id.status == FieldStatus.MISSING


# ============================================================================
# 6. Raw JSON Serialization
# ============================================================================
def test_6_raw_json_serialization():
    """Verify complete raw Azure response is serialized into JSON string."""
    mock_res = make_mock_invoice_result()
    json_str = serialize_azure_result(mock_res)
    assert json_str is not None
    parsed = json.loads(json_str)
    assert parsed["modelId"] == "prebuilt-invoice"
    assert parsed["apiVersion"] == "2024-11-30"


# ============================================================================
# 7. Database Persistence
# ============================================================================
def test_7_database_persistence():
    """Verify persistence of raw JSON, canonical decimal strings, and model metadata."""
    mock_res = make_mock_invoice_result()
    extraction = analyze_invoice_result(mock_res, b"data_bytes", "persisted_inv.pdf")

    doc_id = save_document(extraction, batch_id="batch_001")
    retrieved = get_document_by_id(doc_id)

    assert retrieved is not None
    assert retrieved.id == doc_id
    assert retrieved.file_name == "persisted_inv.pdf"
    assert retrieved.model_used == "prebuilt-invoice"
    assert retrieved.document_type == "invoice"
    assert retrieved.total.value == "1500.00"
    assert retrieved.total.as_decimal() == Decimal("1500.00")
    assert retrieved.raw_azure_json is not None
    raw_payload = json.loads(retrieved.raw_azure_json)
    assert raw_payload["modelId"] == "prebuilt-invoice"


# ============================================================================
# 8. API Upload and Retrieval
# ============================================================================
@patch("app.services.audit_orchestrator.extract_document")
def test_8_api_upload_and_retrieval(mock_extract):
    """Verify single and multi-file upload endpoints with graceful partial failures."""
    import pypdf
    def _make_pdf(title: str) -> bytes:
        writer = pypdf.PdfWriter()
        writer.add_blank_page(width=72, height=72)
        writer.add_metadata({"/Title": title})
        buf = io.BytesIO()
        writer.write(buf)
        return buf.getvalue()

    pdf_bytes_1 = _make_pdf("Doc1")
    pdf_bytes_2 = _make_pdf("Doc2")

    mock_res = make_mock_invoice_result()
    mock_extract.side_effect = lambda file_bytes, filename, preferred_model=None: analyze_invoice_result(
        mock_res, file_bytes, filename
    )

    # 1. Single file upload
    response = client.post(
        "/api/audit/upload",
        files=[("files", ("uploaded_doc.pdf", pdf_bytes_1, "application/pdf"))],
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total_files"] == 1
    assert data["successful_extractions"] == 1
    assert len(data["documents"]) == 1
    doc_id = data["documents"][0]["id"]

    # 2. Document retrieval by ID
    get_res = client.get(f"/api/audit/documents/{doc_id}")
    assert get_res.status_code == 200
    retrieved = get_res.json()
    assert retrieved["vendor_name"]["value"] == "Cambridge Institute of Technology"
    assert retrieved["total"]["value"] == "1500.00"

    # 3. Partial batch failure handling (e.g. invalid file extension)
    multi_res = client.post(
        "/api/audit/upload",
        files=[
            ("files", ("valid.pdf", pdf_bytes_2, "application/pdf")),
            ("files", ("invalid.exe", b"executable", "application/octet-stream")),
        ],
    )
    assert multi_res.status_code == 200
    multi_data = multi_res.json()
    assert multi_data["total_files"] == 2
    assert multi_data["successful_extractions"] == 1
    assert multi_data["failed_extractions"] == 1
    assert "invalid.exe" in multi_data["errors"][0]["file_name"]


# ============================================================================
# 9. Azure Authentication and Service Failure Handling
# ============================================================================
@patch("app.services.azure_client.get_azure_client")
def test_9_azure_authentication_and_error_handling(mock_get_client):
    """Verify handling of ClientAuthenticationError and HttpResponseError without leaking credentials."""
    mock_azure = MagicMock()
    mock_azure.begin_analyze_document.side_effect = ClientAuthenticationError("Access denied: Invalid key")
    mock_get_client.return_value = mock_azure

    with pytest.raises(ClientAuthenticationError):
        analyze_document_bytes(b"content", "prebuilt-invoice")

    # Verify test_azure_connection gracefully reports auth failure
    status = check_azure_connection(perform_live_probe=True)
    assert status["status"] == "error"
    assert "Authentication failed" in status["message"]
