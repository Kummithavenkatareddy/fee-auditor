import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.db.session import init_db
from app.db.repository import save_document, delete_all_documents
from app.schemas.document import DocumentExtraction, ExtractedField, ValidationFlag

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_db():
    init_db()
    delete_all_documents()
    yield
    delete_all_documents()


def test_health_endpoint():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "online"
    assert "azure_configured" in data
    assert "academic_term" in data


def test_document_lifecycle_and_review():
    doc = DocumentExtraction(
        file_name="sample_invoice.pdf",
        file_hash="hash_lifecycle_123",
        vendor_name=ExtractedField(value="Stanford University Press", confidence=0.98),
        invoice_id=ExtractedField(value="INV-STAN-101", confidence=0.99),
        invoice_date=ExtractedField(value="2026-09-01", confidence=0.95),
        vendor_tax_id=ExtractedField(value="US-TAX-888999", confidence=0.90),
        subtotal=ExtractedField(value=100.0, confidence=0.95),
        tax=ExtractedField(value=10.0, confidence=0.95),
        total=ExtractedField(value=110.0, confidence=0.95),
        audit_status="flagged",
        validation_flags=[
            ValidationFlag(
                rule_id="V05",
                rule_name="Low Confidence",
                severity="WARNING",
                field_name="vendor_tax_id",
                reason="Simulated low confidence warning",
                expected_value=">= 0.85",
                actual_value="0.80",
            )
        ],
        created_at="2026-09-01T10:00:00Z",
    )
    doc_id = save_document(doc)

    # 1. Fetch all documents
    res_list = client.get("/api/audit/documents")
    assert res_list.status_code == 200
    docs = res_list.json()
    assert len(docs) == 1
    assert docs[0]["id"] == doc_id
    assert docs[0]["vendor_name"]["value"] == "Stanford University Press"
    assert len(docs[0]["validation_flags"]) == 1

    # 2. Fetch single document
    res_single = client.get(f"/api/audit/documents/{doc_id}")
    assert res_single.status_code == 200
    single_doc = res_single.json()
    assert single_doc["invoice_id"]["value"] == "INV-STAN-101"

    # 3. Update manual review
    review_res = client.patch(
        f"/api/audit/documents/{doc_id}/review",
        json={"manual_review_status": "approved", "notes": "Approved by auditor after verification."},
    )
    assert review_res.status_code == 200
    assert review_res.json()["status"] == "approved"

    # 4. Check summary
    sum_res = client.get("/api/audit/summary")
    assert sum_res.status_code == 200
    summary = sum_res.json()
    assert summary["total_documents"] == 1
    assert summary["total_value"] == 110.0

    # 5. Export CSV
    csv_res = client.get("/api/audit/export/csv")
    assert csv_res.status_code == 200
    assert "text/csv" in csv_res.headers["content-type"]
    csv_text = csv_res.text
    assert "Document ID" in csv_text
    assert "Stanford University Press" in csv_text
    assert "INV-STAN-101" in csv_text
    assert "Approved by auditor" in csv_text
