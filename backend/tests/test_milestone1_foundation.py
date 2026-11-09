import sys
import os
import sqlite3
from decimal import Decimal
import pytest

from app.config import settings
from app.services.azure_client import test_azure_connection as check_azure_connection
from app.schemas.common import (
    FieldStatus,
    ExtractedField,
    ExtractedLineItem,
    ValidationFlag,
    format_canonical_decimal,
)
from app.schemas.invoice import InvoiceData
from app.schemas.receipt import ReceiptData
from app.schemas.document import DocumentExtraction
from app.db.session import init_db, get_db_path, get_db_connection
from app.db.repository import (
    save_document,
    get_document_by_id,
    get_all_documents,
    get_dashboard_summary,
    delete_all_documents,
    normalize_business_key,
)


def test_python_environment_version():
    """Verify runtime Python environment meets project compatibility."""
    major, minor = sys.version_info.major, sys.version_info.minor
    # We require Python 3.10+ (host is Python 3.14.3)
    assert major == 3
    assert minor >= 10
    print(f"Verified Python version: {sys.version.split()[0]}")


def test_dependencies_installed():
    """Verify that all core project dependencies are importable."""
    import fastapi
    import uvicorn
    import pydantic
    import pandas
    import reportlab
    import tenacity
    import azure.ai.documentintelligence

    assert hasattr(fastapi, "__version__")
    assert hasattr(pydantic, "__version__")
    assert hasattr(pandas, "__version__")
    assert hasattr(azure.ai.documentintelligence, "__version__")


def test_secure_azure_configuration():
    """Verify that Azure Document Intelligence configuration is valid without leaking secrets."""
    # Ensure endpoint and key are configured
    assert settings.AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT != ""
    assert settings.AZURE_DOCUMENT_INTELLIGENCE_KEY != ""

    status = check_azure_connection()
    assert status["status"] == "ok"
    assert status["connected"] is True
    assert status["api_version"] == "2024-11-30"

    # Crucial security check: Ensure the secret API key is NOT leaked anywhere in status dict
    status_str = str(status)
    assert settings.AZURE_DOCUMENT_INTELLIGENCE_KEY not in status_str


def test_invoice_and_receipt_schemas_and_decimal_precision():
    """Verify dual schema models and canonical decimal precision."""
    # Test canonical decimal formatting
    assert format_canonical_decimal(1500) == "1500.00"
    assert format_canonical_decimal(120.456) == "120.46"
    assert format_canonical_decimal("$1,234.50") == "1234.50"
    assert format_canonical_decimal(None) is None

    # Test ExtractedField Decimal conversion
    field_money = ExtractedField(value="1500.00", confidence=0.98)
    assert field_money.as_decimal() == Decimal("1500.00")
    assert isinstance(field_money.as_decimal(), Decimal)

    # Test FieldStatus differentiation
    field_na = ExtractedField(value=None, status=FieldStatus.NOT_APPLICABLE)
    assert field_na.status == FieldStatus.NOT_APPLICABLE

    # Test InvoiceData
    inv_data = InvoiceData(
        vendor_name=ExtractedField(value="Tech Academy Supplies", confidence=0.97),
        vendor_tax_id=ExtractedField(value="99-8877665", confidence=0.95),
        invoice_id=ExtractedField(value="INV-2026-001", confidence=0.99),
        total=ExtractedField(value="1500.00", confidence=0.98),
        line_items=[
            ExtractedLineItem(item_index=0, description="Lab Kit", quantity="1.00", unit_price="1500.00", amount="1500.00")
        ],
    )
    assert inv_data.vendor_tax_id.value == "99-8877665"
    assert inv_data.line_items[0].amount_as_decimal() == Decimal("1500.00")

    # Test ReceiptData (merchant name, tax NA, items)
    rec_data = ReceiptData(
        merchant_name=ExtractedField(value="Campus Cafe", confidence=0.96),
        total=ExtractedField(value="15.50", confidence=0.95),
        items=[
            ExtractedLineItem(item_index=0, description="Sandwich", quantity="1.00", amount="15.50")
        ],
    )
    assert rec_data.merchant_name.value == "Campus Cafe"


def test_sqlite_schema_text_money_and_raw_json():
    """Verify SQLite initialization, column data types (TEXT for money), and persistence."""
    init_db()
    delete_all_documents()
    db_file = get_db_path()
    assert db_file.exists()

    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Check table schema column types
        cursor.execute("PRAGMA table_info(documents);")
        columns = {row["name"]: row["type"] for row in cursor.fetchall()}

        # Verify money columns are strictly TEXT (not REAL!)
        assert columns["subtotal"] == "TEXT"
        assert columns["tax"] == "TEXT"
        assert columns["total"] == "TEXT"
        # Verify auditability columns
        assert columns["raw_azure_json"] == "TEXT"
        assert columns["normalized_json"] == "TEXT"
        assert columns["is_business_duplicate"] == "INTEGER"

        # Check line_items column types
        cursor.execute("PRAGMA table_info(line_items);")
        li_columns = {row["name"]: row["type"] for row in cursor.fetchall()}
        assert li_columns["amount"] == "TEXT"
        assert li_columns["unit_price"] == "TEXT"
        assert li_columns["quantity"] == "TEXT"

    # Test Document Persistence and Exact Decimal Retrieval
    doc = DocumentExtraction(
        file_name="tuition_receipt.pdf",
        file_hash="sha256_mock_hash_9999",
        document_type="invoice",
        vendor_name=ExtractedField(value="Cambridge Tech", confidence=0.95),
        invoice_id=ExtractedField(value="CIT-2026-901", confidence=0.98),
        subtotal=ExtractedField(value="1500.00", confidence=0.95),
        tax=ExtractedField(value="0.00", confidence=0.95),
        total=ExtractedField(value="1500.00", confidence=0.98),
        line_items=[
            ExtractedLineItem(description="Tuition", amount="1500.00", confidence=0.95)
        ],
        raw_azure_json='{"status": "succeeded", "modelId": "prebuilt-invoice"}',
        created_at="2026-11-07T08:00:00Z",
    )

    doc_id = save_document(doc)
    retrieved = get_document_by_id(doc_id)

    assert retrieved is not None
    assert retrieved.total.value == "1500.00"
    assert retrieved.total.as_decimal() == Decimal("1500.00")
    assert retrieved.line_items[0].amount == "1500.00"
    assert retrieved.line_items[0].amount_as_decimal() == Decimal("1500.00")
    assert retrieved.raw_azure_json == '{"status": "succeeded", "modelId": "prebuilt-invoice"}'

    # Test business key normalization
    key = normalize_business_key(" Cambridge Tech  ", " #CIT-2026-901 ")
    assert key == ("cambridge tech", "CIT2026901")

    # Test Summary Decimal precision
    summary = get_dashboard_summary()
    assert summary.total_documents >= 1
    assert summary.total_value == 1500.00

    # Cleanup
    delete_all_documents()
