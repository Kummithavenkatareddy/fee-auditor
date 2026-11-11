import io
import uuid
from typing import Dict, Any, List
from unittest.mock import patch, MagicMock
import pytest
from fastapi.testclient import TestClient

import pypdf
from reportlab.pdfgen import canvas
from PIL import Image

from app.main import app
from app.config import settings
from app.db.session import get_db_connection
from app.schemas.common import ExtractedField, FieldStatus
from app.schemas.document import DocumentExtraction
from app.services.content_safety import (
    ContentSafetyService,
    content_safety_service,
    STANDARD_CATEGORIES,
)
from app.db.repository import get_content_safety_events, delete_all_documents

client = TestClient(app)


# ============================================================================
# Test Helpers
# ============================================================================
class MockCategoryAnalysis:
    def __init__(self, category: str, severity: int):
        self.category = category
        self.severity = severity


class MockAnalyzeTextResult:
    def __init__(self, severities: Dict[str, int], blocklists_match=None):
        self.categories_analysis = [
            MockCategoryAnalysis(cat, sev) for cat, sev in severities.items()
        ]
        self.blocklists_match = blocklists_match or []


class MockAnalyzeImageResult:
    def __init__(self, severities: Dict[str, int]):
        self.categories_analysis = [
            MockCategoryAnalysis(cat, sev) for cat, sev in severities.items()
        ]


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


def create_pdf_with_pages(pages_text: List[str]) -> bytes:
    """Generate a valid multi-page PDF with extractable text using reportlab."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    for text in pages_text:
        c.drawString(100, 700, text)
        c.showPage()
    c.save()
    return buf.getvalue()


def create_encrypted_pdf() -> bytes:
    """Generate a password-protected valid PDF."""
    raw_pdf = create_pdf_with_pages(["Secret encrypted confidential document."])
    reader = pypdf.PdfReader(io.BytesIO(raw_pdf))
    writer = pypdf.PdfWriter()
    writer.append(reader)
    writer.encrypt("topsecret123")
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def create_test_image_bytes(color=None, size=(100, 100)) -> bytes:
    """Generate valid JPEG image bytes with unique pixel data using PIL."""
    if color is None:
        import random
        color = (random.randint(1, 254), random.randint(1, 254), random.randint(1, 254))
    img = Image.new("RGB", size, color=color)
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def make_mock_invoice_extraction(filename: str = "INV-001.pdf") -> DocumentExtraction:
    """Create a mock successful DocumentExtraction."""
    return DocumentExtraction(
        id=str(uuid.uuid4()),
        file_name=filename,
        file_hash="test_hash_" + str(uuid.uuid4()),
        model_used="prebuilt-invoice",
        document_type="invoice",
        extraction_status="succeeded",
        audit_status="clean",
        vendor_name=ExtractedField(value="National Institute of Engineering", confidence=0.99, status=FieldStatus.EXTRACTED),
        invoice_id=ExtractedField(value="NIE-2026-001", confidence=0.98, status=FieldStatus.EXTRACTED),
        invoice_date=ExtractedField(value="2026-09-15", confidence=0.97, status=FieldStatus.EXTRACTED),
        subtotal=ExtractedField(value="10000.00", confidence=0.99, status=FieldStatus.EXTRACTED),
        tax=ExtractedField(value="1800.00", confidence=0.98, status=FieldStatus.EXTRACTED),
        total=ExtractedField(value="11800.00", confidence=0.99, status=FieldStatus.EXTRACTED),
    )


# ============================================================================
# Scenario 1: Clean Invoice Accepted
# ============================================================================
def test_01_clean_invoice_accepted():
    user = register_and_login_user(f"cs_user_01_{uuid.uuid4()}@university.edu")
    pdf_bytes = create_pdf_with_pages([
        "Invoice: INV-2026-001\nVendor: Cambridge Institute of Technology\nTotal: 1500.00"
    ])
    mock_doc = make_mock_invoice_extraction("clean_invoice.pdf")

    mock_text_res = MockAnalyzeTextResult({c: 0 for c in STANDARD_CATEGORIES})
    mock_img_res = MockAnalyzeImageResult({c: 0 for c in STANDARD_CATEGORIES})

    with patch.object(content_safety_service, "_client") as mock_client, \
         patch("app.services.audit_orchestrator.extract_document", return_value=mock_doc):
        mock_client.analyze_text.return_value = mock_text_res
        mock_client.analyze_image.return_value = mock_img_res

        res = client.post(
            "/api/audit/upload",
            headers=user["headers"],
            files=[("files", ("clean_invoice.pdf", pdf_bytes, "application/pdf"))],
        )

    assert res.status_code == 200
    data = res.json()
    assert data["successful_extractions"] == 1
    assert data["rejected_by_content_safety"] == 0
    assert data["screening_failed"] == 0
    assert len(data["documents"]) == 1
    doc = data["documents"][0]
    assert doc["content_safety_status"] == "passed"
    assert doc["content_safety"]["is_safe"] is True
    assert doc["content_safety"]["highest_severity"] == 0


# ============================================================================
# Scenario 2: Clean Receipt Accepted
# ============================================================================
def test_02_clean_receipt_accepted():
    user = register_and_login_user(f"cs_user_02_{uuid.uuid4()}@university.edu")
    img_bytes = create_test_image_bytes()
    mock_doc = make_mock_invoice_extraction("clean_receipt.jpg")
    mock_doc.document_type = "receipt"

    mock_img_res = MockAnalyzeImageResult({c: 0 for c in STANDARD_CATEGORIES})

    with patch.object(content_safety_service, "_client") as mock_client, \
         patch("app.services.audit_orchestrator.extract_document", return_value=mock_doc):
        mock_client.analyze_image.return_value = mock_img_res

        res = client.post(
            "/api/audit/upload",
            headers=user["headers"],
            files=[("files", ("clean_receipt.jpg", img_bytes, "image/jpeg"))],
        )

    assert res.status_code == 200
    data = res.json()
    assert data["successful_extractions"] == 1
    assert data["rejected_by_content_safety"] == 0
    assert len(data["documents"]) == 1
    assert data["documents"][0]["content_safety_status"] == "passed"


# ============================================================================
# Scenario 3: Sexually Explicit Text Rejected
# ============================================================================
def test_03_sexually_explicit_text_rejected():
    user = register_and_login_user(f"cs_user_03_{uuid.uuid4()}@university.edu")
    pdf_bytes = create_pdf_with_pages(["Inappropriate sexual text in document."])

    # Sexual category severity 4 (threshold is 4)
    mock_text_res = MockAnalyzeTextResult({
        "Sexual": 4,
        "Hate": 0,
        "Violence": 0,
        "SelfHarm": 0,
    })
    mock_img_res = MockAnalyzeImageResult({c: 0 for c in STANDARD_CATEGORIES})

    with patch.object(content_safety_service, "_client") as mock_client, \
         patch("app.services.audit_orchestrator.extract_document") as mock_extract:
        mock_client.analyze_text.return_value = mock_text_res
        mock_client.analyze_image.return_value = mock_img_res

        res = client.post(
            "/api/audit/upload",
            headers=user["headers"],
            files=[("files", ("unsafe_sexual.pdf", pdf_bytes, "application/pdf"))],
        )

    assert res.status_code == 200
    data = res.json()
    assert data["successful_extractions"] == 0
    assert data["rejected_by_content_safety"] == 1
    assert len(data["rejected_documents"]) == 1
    rej = data["rejected_documents"][0]
    assert rej["file_name"] == "unsafe_sexual.pdf"
    assert rej["status"] == "rejected"
    assert rej["detected_category"] == "Sexual"
    assert rej["severity"] == 4
    assert "Sexual" in rej["reason"]

    # Extraction must NEVER be called
    mock_extract.assert_not_called()


# ============================================================================
# Scenario 4: Harmful Image Rejected
# ============================================================================
def test_04_harmful_image_rejected():
    user = register_and_login_user(f"cs_user_04_{uuid.uuid4()}@university.edu")
    img_bytes = create_test_image_bytes()

    # Image returns Violence severity 6
    mock_img_res = MockAnalyzeImageResult({
        "Violence": 6,
        "Sexual": 0,
        "Hate": 0,
        "SelfHarm": 0,
    })

    with patch.object(content_safety_service, "_client") as mock_client, \
         patch("app.services.audit_orchestrator.extract_document") as mock_extract:
        mock_client.analyze_image.return_value = mock_img_res

        res = client.post(
            "/api/audit/upload",
            headers=user["headers"],
            files=[("files", ("violent_scene.png", img_bytes, "image/png"))],
        )

    assert res.status_code == 200
    data = res.json()
    assert data["successful_extractions"] == 0
    assert data["rejected_by_content_safety"] == 1
    assert len(data["rejected_documents"]) == 1
    rej = data["rejected_documents"][0]
    assert rej["detected_category"] == "Violence"
    assert rej["severity"] == 6
    assert "Violence" in rej["reason"]
    mock_extract.assert_not_called()


# ============================================================================
# Scenario 5: Custom Profanity Blocklist Match
# ============================================================================
def test_05_custom_profanity_blocklist_match():
    user = register_and_login_user(f"cs_user_05_{uuid.uuid4()}@university.edu")
    pdf_bytes = create_pdf_with_pages(["Item description contains profanity_term_xyz in line item."])

    original_terms = settings.CONTENT_SAFETY_CUSTOM_TERMS
    try:
        settings.CONTENT_SAFETY_CUSTOM_TERMS = "profanity_term_xyz,prohibited_word"
        with patch("app.services.audit_orchestrator.extract_document") as mock_extract:
            res = client.post(
                "/api/audit/upload",
                headers=user["headers"],
                files=[("files", ("profane_invoice.pdf", pdf_bytes, "application/pdf"))],
            )

        assert res.status_code == 200
        data = res.json()
        assert data["successful_extractions"] == 0
        assert data["rejected_by_content_safety"] == 1
        assert len(data["rejected_documents"]) == 1
        rej = data["rejected_documents"][0]
        assert rej["status"] == "rejected"
        assert "profanity_term_xyz" in rej["reason"]
        mock_extract.assert_not_called()
    finally:
        settings.CONTENT_SAFETY_CUSTOM_TERMS = original_terms


# ============================================================================
# Scenario 6: Multi-Page PDF with One Unsafe Page Rejected
# ============================================================================
def test_06_multipage_pdf_one_unsafe_page_rejected():
    user = register_and_login_user(f"cs_user_06_{uuid.uuid4()}@university.edu")
    # Page 1 clean, Page 2 clean text but page 2 image contains Hate
    pdf_bytes = create_pdf_with_pages([
        "Page 1: Institutional Tuition Fee Summary",
        "Page 2: Schedule of Additional Miscellaneous Dues",
    ])

    call_count = 0

    def mock_image_analysis(options, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            # Page 1 image clean
            return MockAnalyzeImageResult({c: 0 for c in STANDARD_CATEGORIES})
        else:
            # Page 2 image flagged for Hate severity 4
            return MockAnalyzeImageResult({"Hate": 4, "Sexual": 0, "Violence": 0, "SelfHarm": 0})

    mock_text_res = MockAnalyzeTextResult({c: 0 for c in STANDARD_CATEGORIES})

    with patch.object(content_safety_service, "_client") as mock_client, \
         patch("app.services.audit_orchestrator.extract_document") as mock_extract:
        mock_client.analyze_text.return_value = mock_text_res
        mock_client.analyze_image.side_effect = mock_image_analysis

        res = client.post(
            "/api/audit/upload",
            headers=user["headers"],
            files=[("files", ("multipage_document.pdf", pdf_bytes, "application/pdf"))],
        )

    assert res.status_code == 200
    data = res.json()
    assert data["successful_extractions"] == 0
    assert data["rejected_by_content_safety"] == 1
    assert data["rejected_documents"][0]["detected_category"] == "Hate"
    assert data["rejected_documents"][0]["severity"] == 4
    mock_extract.assert_not_called()


# ============================================================================
# Scenario 7: Content Safety Timeout (Fail-Closed)
# ============================================================================
def test_07_content_safety_timeout_fail_closed():
    user = register_and_login_user(f"cs_user_07_{uuid.uuid4()}@university.edu")
    pdf_bytes = create_pdf_with_pages(["Standard Invoice Text."])

    original_policy = settings.CONTENT_SAFETY_FAILURE_POLICY
    try:
        settings.CONTENT_SAFETY_FAILURE_POLICY = "fail_closed"
        content_safety_service.failure_policy = "fail_closed"

        with patch.object(content_safety_service, "_client") as mock_client, \
             patch("app.services.audit_orchestrator.extract_document") as mock_extract:
            mock_client.analyze_text.side_effect = TimeoutError("Content Safety service gateway timeout")

            res = client.post(
                "/api/audit/upload",
                headers=user["headers"],
                files=[("files", ("timeout_invoice.pdf", pdf_bytes, "application/pdf"))],
            )

        assert res.status_code == 200
        data = res.json()
        assert data["successful_extractions"] == 0
        assert data["screening_failed"] == 1
        assert len(data["rejected_documents"]) == 1
        rej = data["rejected_documents"][0]
        assert rej["status"] == "failed"
        assert "failed" in rej["reason"].lower() or "timeout" in rej["reason"].lower()
        mock_extract.assert_not_called()
    finally:
        settings.CONTENT_SAFETY_FAILURE_POLICY = original_policy
        content_safety_service.failure_policy = original_policy


# ============================================================================
# Scenario 8: Corrupt or Encrypted PDF
# ============================================================================
def test_08_corrupt_or_encrypted_pdf():
    user = register_and_login_user(f"cs_user_08_{uuid.uuid4()}@university.edu")

    # 1. Encrypted PDF
    enc_pdf = create_encrypted_pdf()
    with patch("app.services.audit_orchestrator.extract_document") as mock_extract:
        res_enc = client.post(
            "/api/audit/upload",
            headers=user["headers"],
            files=[("files", ("password_locked.pdf", enc_pdf, "application/pdf"))],
        )

    assert res_enc.status_code == 200
    data_enc = res_enc.json()
    assert data_enc["screening_failed"] == 1
    assert data_enc["successful_extractions"] == 0
    assert "encrypted" in data_enc["rejected_documents"][0]["reason"].lower() or "password" in data_enc["rejected_documents"][0]["reason"].lower()
    mock_extract.assert_not_called()

    # 2. Corrupt PDF
    corrupt_bytes = b"%PDF-1.4\nGarbage data without header or trailer or xref table"
    with patch("app.services.audit_orchestrator.extract_document") as mock_extract_2:
        res_corrupt = client.post(
            "/api/audit/upload",
            headers=user["headers"],
            files=[("files", ("corrupted_invoice.pdf", corrupt_bytes, "application/pdf"))],
        )

    assert res_corrupt.status_code == 200
    data_corrupt = res_corrupt.json()
    assert data_corrupt["screening_failed"] == 1
    assert data_corrupt["successful_extractions"] == 0
    assert "corrupt" in data_corrupt["rejected_documents"][0]["reason"].lower() or "unreadable" in data_corrupt["rejected_documents"][0]["reason"].lower()
    mock_extract_2.assert_not_called()


# ============================================================================
# Scenario 9: Legitimate Financial Text Not Incorrectly Rejected
# ============================================================================
def test_09_legitimate_financial_text_not_incorrectly_rejected():
    user = register_and_login_user(f"cs_user_09_{uuid.uuid4()}@university.edu")
    financial_text = (
        "Invoice: INV-FIN-99\n"
        "Late payment penalty: Rs 500\n"
        "Bank transaction charge: Rs 50\n"
        "Gross subtotal: Rs 10000\n"
        "Tax cut discount applied: Rs 200\n"
        "Order execution fee: Rs 150\n"
        "Liquidated damages assessment: Rs 0"
    )
    pdf_bytes = create_pdf_with_pages([financial_text])
    mock_doc = make_mock_invoice_extraction("financial_terms.pdf")

    # Content Safety returns 0 for all categories on legitimate accounting words
    mock_text_res = MockAnalyzeTextResult({c: 0 for c in STANDARD_CATEGORIES})
    mock_img_res = MockAnalyzeImageResult({c: 0 for c in STANDARD_CATEGORIES})

    # Even if custom blocklist terms are set, word boundary matching ensures "cut", "gross", "charge" don't trigger unless exact term is listed
    original_terms = settings.CONTENT_SAFETY_CUSTOM_TERMS
    try:
        settings.CONTENT_SAFETY_CUSTOM_TERMS = "grossness,cutter,charging_bad_word"
        with patch.object(content_safety_service, "_client") as mock_client, \
             patch("app.services.audit_orchestrator.extract_document", return_value=mock_doc):
            mock_client.analyze_text.return_value = mock_text_res
            mock_client.analyze_image.return_value = mock_img_res

            res = client.post(
                "/api/audit/upload",
                headers=user["headers"],
                files=[("files", ("financial_terms.pdf", pdf_bytes, "application/pdf"))],
            )

        assert res.status_code == 200
        data = res.json()
        assert data["successful_extractions"] == 1
        assert data["rejected_by_content_safety"] == 0
        assert data["documents"][0]["content_safety_status"] == "passed"
    finally:
        settings.CONTENT_SAFETY_CUSTOM_TERMS = original_terms


# ============================================================================
# Scenario 10: Safe Document Proceeds to Azure Document Intelligence
# ============================================================================
def test_10_safe_document_proceeds_to_azure_extraction():
    user = register_and_login_user(f"cs_user_10_{uuid.uuid4()}@university.edu")
    pdf_bytes = create_pdf_with_pages(["Clean institutional invoice."])
    mock_doc = make_mock_invoice_extraction("safe_invoice.pdf")

    mock_text_res = MockAnalyzeTextResult({c: 0 for c in STANDARD_CATEGORIES})
    mock_img_res = MockAnalyzeImageResult({c: 0 for c in STANDARD_CATEGORIES})

    with patch.object(content_safety_service, "_client") as mock_client, \
         patch("app.services.audit_orchestrator.extract_document", return_value=mock_doc) as mock_extract:
        mock_client.analyze_text.return_value = mock_text_res
        mock_client.analyze_image.return_value = mock_img_res

        res = client.post(
            "/api/audit/upload",
            headers=user["headers"],
            files=[("files", ("safe_invoice.pdf", pdf_bytes, "application/pdf"))],
        )

    assert res.status_code == 200
    assert mock_extract.called
    assert mock_extract.call_count == 1
    call_args = mock_extract.call_args[1]
    assert call_args["filename"] == "safe_invoice.pdf"


# ============================================================================
# Scenario 11: Unsafe Document Never Reaches Document Intelligence
# ============================================================================
def test_11_unsafe_document_never_reaches_document_intelligence():
    user = register_and_login_user(f"cs_user_11_{uuid.uuid4()}@university.edu")
    pdf_bytes = create_pdf_with_pages(["Extremely toxic hate speech content."])

    mock_text_res = MockAnalyzeTextResult({"Hate": 6, "Sexual": 0, "Violence": 0, "SelfHarm": 0})
    mock_img_res = MockAnalyzeImageResult({c: 0 for c in STANDARD_CATEGORIES})

    with patch.object(content_safety_service, "_client") as mock_client, \
         patch("app.services.audit_orchestrator.extract_document") as mock_extract:
        mock_client.analyze_text.return_value = mock_text_res
        mock_client.analyze_image.return_value = mock_img_res

        res = client.post(
            "/api/audit/upload",
            headers=user["headers"],
            files=[("files", ("hate_speech_doc.pdf", pdf_bytes, "application/pdf"))],
        )

    assert res.status_code == 200
    data = res.json()
    assert data["rejected_by_content_safety"] == 1
    assert data["successful_extractions"] == 0

    # 1. Document Intelligence extract_document was NEVER called
    mock_extract.assert_not_called()

    # 2. SQLite documents table has NO record for this file
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM documents WHERE file_name = 'hate_speech_doc.pdf';")
        assert cursor.fetchone() is None

        # 3. Validation flags table has NO records for this file
        cursor.execute("SELECT id FROM validation_flags WHERE document_id IN (SELECT id FROM documents WHERE file_name = 'hate_speech_doc.pdf');")
        assert len(cursor.fetchall()) == 0

    # 4. Security audit log in content_safety_events HAS the rejection recorded
    events = get_content_safety_events(owner_user_id=user["user"]["id"])
    assert len(events) >= 1
    ev = next(e for e in events if e["file_name"] == "hate_speech_doc.pdf")
    assert ev["status"] == "rejected"
    assert ev["detected_category"] == "Hate"
    assert ev["severity"] == 6
    assert ev["action_taken"] == "rejected"
