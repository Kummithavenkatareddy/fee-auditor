import io
import json
from decimal import Decimal
import pytest
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

from app.schemas.common import FieldStatus
from app.services.azure_client import test_azure_connection as check_azure_conn, analyze_document_bytes
from app.services.extractor import extract_document, compute_file_hash


def create_sample_invoice_pdf() -> bytes:
    """Generate a clean in-memory PDF invoice for live testing."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, 750, "TAX INVOICE")

    c.setFont("Helvetica", 10)
    c.drawString(50, 720, "Vendor: Apex University Bookstore LLC")
    c.drawString(50, 705, "Tax ID: 99-8877665")
    c.drawString(50, 690, "Invoice Date: 2026-09-15")
    c.drawString(50, 675, "Invoice #: INV-2026-8801")

    c.drawString(50, 640, "Bill To: Student Accounts Department")
    c.drawString(50, 625, "Term: Fall 2026")

    # Table Header
    c.line(50, 610, 500, 610)
    c.drawString(50, 595, "Description")
    c.drawString(300, 595, "Qty")
    c.drawString(370, 595, "Unit Price")
    c.drawString(450, 595, "Amount")
    c.line(50, 585, 500, 585)

    # Line Items
    c.drawString(50, 570, "Advanced AI Engineering Textbook")
    c.drawString(300, 570, "1")
    c.drawString(370, 570, "$120.00")
    c.drawString(450, 570, "$120.00")

    c.drawString(50, 550, "Laboratory Notebook & Safety Pack")
    c.drawString(300, 550, "2")
    c.drawString(370, 550, "$25.00")
    c.drawString(450, 550, "$50.00")

    c.line(50, 535, 500, 535)

    # Totals
    c.drawString(350, 515, "Subtotal:")
    c.drawString(450, 515, "$170.00")
    c.drawString(350, 495, "Tax (10%):")
    c.drawString(450, 495, "$17.00")
    c.setFont("Helvetica-Bold", 11)
    c.drawString(350, 475, "Total:")
    c.drawString(450, 475, "$187.00")

    c.showPage()
    c.save()
    buf.seek(0)
    return buf.getvalue()


def create_sample_receipt_pdf() -> bytes:
    """Generate a clean in-memory PDF receipt for live receipt model testing."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(100, 750, "CAMPUS BOOKSTORE RECEIPT")

    c.setFont("Helvetica", 10)
    c.drawString(100, 730, "Merchant: University Campus Bookstore")
    c.drawString(100, 715, "Address: 100 University Ave, Cambridge, MA")
    c.drawString(100, 700, "Date: 2026-10-05")

    c.line(100, 685, 400, 685)
    c.drawString(100, 670, "Scientific Graphing Calculator")
    c.drawRightString(400, 670, "$115.00")
    c.drawString(100, 650, "Distributed Systems Handbook")
    c.drawRightString(400, 650, "$85.00")
    c.line(100, 635, 400, 635)

    c.drawString(250, 615, "Subtotal:")
    c.drawRightString(400, 615, "$200.00")
    c.drawString(250, 595, "Tax:")
    c.drawRightString(400, 595, "$16.00")
    c.setFont("Helvetica-Bold", 11)
    c.drawString(250, 575, "Total:")
    c.drawRightString(400, 575, "$216.00")

    c.showPage()
    c.save()
    buf.seek(0)
    return buf.getvalue()


def test_azure_connection_status():
    """Verify that Azure connection configuration is valid."""
    status = check_azure_conn()
    assert status["status"] == "ok"
    assert status["connected"] is True
    assert status["api_version"] == "2024-11-30"


def test_file_hash_computation():
    """Verify deterministic SHA-256 computation."""
    data = b"Sample document bytes"
    h1 = compute_file_hash(data)
    h2 = compute_file_hash(data)
    assert h1 == h2
    assert len(h1) == 64


def test_live_invoice_extraction():
    """Send a generated sample invoice to Azure and verify normalized extraction."""
    pdf_bytes = create_sample_invoice_pdf()
    extraction = extract_document(
        file_bytes=pdf_bytes,
        filename="live_test_invoice.pdf",
        preferred_model="prebuilt-invoice",
    )

    # Basic validations
    assert extraction.file_name == "live_test_invoice.pdf"
    assert extraction.model_used == "prebuilt-invoice"
    assert extraction.document_type == "invoice"
    assert extraction.invoice_data is not None
    assert extraction.file_hash is not None

    # Check extracted vendor
    assert extraction.vendor_name.value is not None
    assert "Apex" in extraction.vendor_name.value
    assert extraction.vendor_name.confidence is not None
    assert extraction.vendor_name.confidence > 0.7

    # Check invoice id
    assert extraction.invoice_id.value is not None
    assert "8801" in extraction.invoice_id.value

    # Check canonical decimal string total
    assert extraction.total.value == "187.00"
    assert extraction.total.as_decimal() == Decimal("187.00")

    # Check raw Azure JSON presence
    assert extraction.raw_azure_json is not None
    raw_data = json.loads(extraction.raw_azure_json)
    assert "documents" in raw_data or "status" in raw_data or "modelId" in raw_data


def test_live_receipt_extraction():
    """Send a generated sample receipt to Azure prebuilt-receipt model."""
    pdf_bytes = create_sample_receipt_pdf()
    extraction = extract_document(
        file_bytes=pdf_bytes,
        filename="campus_bookstore_receipt.pdf",
        preferred_model="prebuilt-receipt",
    )

    assert extraction.file_name == "campus_bookstore_receipt.pdf"
    assert extraction.model_used == "prebuilt-receipt"
    assert extraction.document_type == "receipt"
    assert extraction.receipt_data is not None

    # Check merchant
    assert extraction.vendor_name.value is not None
    assert "Bookstore" in extraction.vendor_name.value

    # Check that tax ID is marked NOT_APPLICABLE on receipts
    assert extraction.vendor_tax_id.status == FieldStatus.NOT_APPLICABLE
    assert extraction.vendor_tax_id.value is None

    # Check canonical decimal total
    assert extraction.total.value == "216.00"
    assert extraction.total.as_decimal() == Decimal("216.00")
