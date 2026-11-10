import io
import uuid
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.config import settings
from app.db.session import get_db_connection
from app.schemas.common import FieldStatus, ExtractedField
from app.schemas.document import DocumentExtraction

client = TestClient(app)
DEPLOYED_FRONTEND = "https://fee-auditor-frontend.vercel.app"


def test_cors_preflight_for_deployed_frontend():
    """Verify that OPTIONS preflight requests from the deployed frontend origin succeed with correct headers."""
    response = client.options(
        "/api/audit/summary",
        headers={
            "Origin": DEPLOYED_FRONTEND,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == DEPLOYED_FRONTEND
    assert response.headers.get("access-control-allow-credentials") == "true"
    allow_methods = response.headers.get("access-control-allow-methods", "")
    assert "GET" in allow_methods
    assert "POST" in allow_methods
    assert "PATCH" in allow_methods
    assert "DELETE" in allow_methods


def test_e2e_complete_deployed_workflow():
    """
    End-to-end simulation of deployed frontend interacting with deployed backend:
    - User registration, verification, login, profile
    - Document upload with Content Safety & Azure extraction
    - Document ledger & detail retrieval
    - Cross-domain file binary streaming with query token
    - Manual review decisioning
    - Relational dashboard summary
    - CSV report export
    - Level 1 exact duplicate prevention
    - Strict multi-user data isolation
    - Data reset and account cleanup
    """
    import pypdf
    from reportlab.pdfgen import canvas

    def make_pdf(title: str) -> bytes:
        buf = io.BytesIO()
        c = canvas.Canvas(buf)
        c.drawString(100, 700, f"Invoice: {title}")
        c.drawString(100, 670, "Vendor: National Research Institute")
        c.drawString(100, 640, "Total: Rs 5,000.00")
        c.showPage()
        c.save()
        return buf.getvalue()

    # 1. Register User A
    user_a_email = f"deploy_a_{uuid.uuid4().hex[:6]}@university.edu"
    reg_a = client.post(
        "/api/auth/register",
        json={"identifier": user_a_email, "password": "SecurePassword123!", "full_name": "Auditor Alpha"},
        headers={"Origin": DEPLOYED_FRONTEND},
    )
    assert reg_a.status_code == 201
    code_a = reg_a.json().get("dev_verification_code", "000000")

    # 2. Verify User A
    ver_a = client.post(
        "/api/auth/verify",
        json={"identifier": user_a_email, "code": code_a},
        headers={"Origin": DEPLOYED_FRONTEND},
    )
    assert ver_a.status_code == 200
    token_a = ver_a.json()["access_token"]
    headers_a = {
        "Authorization": f"Bearer {token_a}",
        "Origin": DEPLOYED_FRONTEND,
    }

    # 3. Verify session
    me_a = client.get("/api/auth/me", headers=headers_a)
    assert me_a.status_code == 200
    assert me_a.json()["identifier"] == user_a_email

    # 4. Upload document
    pdf_bytes = make_pdf("TUITION-2026-A1")
    upload_res = client.post(
        "/api/audit/upload",
        files=[("files", ("tuition_a1.pdf", pdf_bytes, "application/pdf"))],
        headers=headers_a,
    )
    assert upload_res.status_code == 200
    data = upload_res.json()
    assert data["successful_extractions"] == 1
    doc_id = data["documents"][0]["id"]

    # 5. Document ledger
    list_res = client.get("/api/audit/documents", headers=headers_a)
    assert list_res.status_code == 200
    docs = list_res.json()
    assert any(d["id"] == doc_id for d in docs)

    # 6. Single document detail
    detail_res = client.get(f"/api/audit/documents/{doc_id}", headers=headers_a)
    assert detail_res.status_code == 200
    assert detail_res.json()["file_name"] == "tuition_a1.pdf"

    # 7. Cross-domain file streaming with query parameter token
    file_res = client.get(
        f"/api/audit/documents/{doc_id}/file?token={token_a}",
        headers={"Origin": DEPLOYED_FRONTEND},
    )
    assert file_res.status_code == 200
    assert len(file_res.content) > 0

    # 8. Manual Review
    rev_res = client.patch(
        f"/api/audit/documents/{doc_id}/review",
        json={"manual_review_status": "approved", "notes": "Approved via deployed UI"},
        headers=headers_a,
    )
    assert rev_res.status_code == 200
    assert rev_res.json()["status"] == "approved"

    # 9. Dashboard Summary
    sum_res = client.get("/api/audit/summary", headers=headers_a)
    assert sum_res.status_code == 200
    assert sum_res.json()["total_documents"] >= 1

    # 10. CSV Export
    csv_res = client.get("/api/audit/export/csv", headers=headers_a)
    assert csv_res.status_code == 200
    assert "text/csv" in csv_res.headers.get("content-type", "")

    # 11. Level 1 Exact Duplicate
    dup_res = client.post(
        "/api/audit/upload",
        files=[("files", ("tuition_a1.pdf", pdf_bytes, "application/pdf"))],
        headers=headers_a,
    )
    assert dup_res.status_code == 200
    assert dup_res.json()["duplicate_files"] == 1

    # 12. Register User B and verify multi-user isolation
    user_b_email = f"deploy_b_{uuid.uuid4().hex[:6]}@university.edu"
    reg_b = client.post(
        "/api/auth/register",
        json={"identifier": user_b_email, "password": "SecurePassword123!"},
        headers={"Origin": DEPLOYED_FRONTEND},
    )
    ver_b = client.post(
        "/api/auth/verify",
        json={"identifier": user_b_email, "code": reg_b.json().get("dev_verification_code", "000000")},
        headers={"Origin": DEPLOYED_FRONTEND},
    )
    headers_b = {
        "Authorization": f"Bearer {ver_b.json()['access_token']}",
        "Origin": DEPLOYED_FRONTEND,
    }

    # User B must NOT see User A's document
    doc_b_view = client.get(f"/api/audit/documents/{doc_id}", headers=headers_b)
    assert doc_b_view.status_code in (404, 401, 403)

    list_b = client.get("/api/audit/documents", headers=headers_b)
    assert list_b.status_code == 200
    assert not any(d["id"] == doc_id for d in list_b.json())

    # 13. Delete document
    del_res = client.delete(f"/api/audit/documents/{doc_id}", headers=headers_a)
    assert del_res.status_code == 200

    # 14. Reset data and delete account
    reset_res = client.post(
        "/api/users/reset-data",
        json={"password": "SecurePassword123!", "confirmation_phrase": "RESET"},
        headers=headers_a,
    )
    assert reset_res.status_code == 200

    del_acc = client.request(
        "DELETE",
        "/api/users/account",
        json={"password": "SecurePassword123!", "confirmation_phrase": "DELETE"},
        headers=headers_a,
    )
    assert del_acc.status_code == 200

