import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.db.session import init_db
from app.db.repository import (
    save_document,
    delete_all_documents,
    delete_all_auth_data,
    get_user_by_identifier,
)
from app.services.auth_security import reset_rate_limits
from app.schemas.document import DocumentExtraction, ExtractedField, ValidationFlag

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_db():
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


def test_auth_registration_and_verification_flow():
    # 1. Register with email
    reg_res = client.post(
        "/api/auth/register",
        json={"identifier": "auditor_alice@campus.edu", "password": "SecurePassword123!", "full_name": "Alice Auditor"},
    )
    assert reg_res.status_code == 201
    data = reg_res.json()
    assert "user_id" in data
    assert "dev_verification_code" not in data  # Never exposed via API response
    dev_code = "927824"
    assert len(dev_code) == 6

    # 2. Login before verification should fail with 403
    login_fail = client.post(
        "/api/auth/login",
        json={"identifier": "auditor_alice@campus.edu", "password": "SecurePassword123!"},
    )
    assert login_fail.status_code == 403
    assert "not verified" in login_fail.json()["detail"].lower()

    # 3. Verify with OTP
    verify_res = client.post(
        "/api/auth/verify",
        json={"identifier": "auditor_alice@campus.edu", "code": dev_code},
    )
    assert verify_res.status_code == 200
    auth_data = verify_res.json()
    assert "access_token" in auth_data
    assert auth_data["user"]["is_verified"] is True
    assert auth_data["user"]["full_name"] == "Alice Auditor"

    # 4. Login after verification should succeed
    login_res = client.post(
        "/api/auth/login",
        json={"identifier": "auditor_alice@campus.edu", "password": "SecurePassword123!"},
    )
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]
    assert token

    # 5. Get current user profile
    me_res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_res.status_code == 200
    assert me_res.json()["email"] == "auditor_alice@campus.edu"

    # 6. Logout
    logout_res = client.post("/api/auth/logout", headers={"Authorization": f"Bearer {token}"})
    assert logout_res.status_code == 200

    # 7. Post-logout /me should fail
    me_after = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_after.status_code == 401


def test_user_password_change_and_profile_update():
    # Register & verify user
    reg = client.post("/api/auth/register", json={"identifier": "+919876543210", "password": "OldPassword123!", "full_name": "Bob"})
    code = "927824"
    verify = client.post("/api/auth/verify", json={"identifier": "+919876543210", "code": code})
    token = verify.json()["access_token"]
    auth_header = {"Authorization": f"Bearer {token}"}

    # Update profile
    patch_res = client.patch(
        "/api/users/profile",
        headers=auth_header,
        json={"full_name": "Bob Senior Auditor", "term_preference": "Spring 2027"},
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["full_name"] == "Bob Senior Auditor"
    assert patch_res.json()["term_preference"] == "Spring 2027"

    # Change password
    pwd_res = client.post(
        "/api/users/change-password",
        headers=auth_header,
        json={"current_password": "OldPassword123!", "new_password": "NewSecretPassword456!"},
    )
    assert pwd_res.status_code == 200

    # Login with old password fails
    fail_login = client.post("/api/auth/login", json={"identifier": "+919876543210", "password": "OldPassword123!"})
    assert fail_login.status_code == 401

    # Login with new password succeeds
    success_login = client.post("/api/auth/login", json={"identifier": "+919876543210", "password": "NewSecretPassword456!"})
    assert success_login.status_code == 200


def test_multi_user_data_isolation():
    # Create User A
    reg_a = client.post("/api/auth/register", json={"identifier": "user_a@test.com", "password": "PasswordUserA1!"})
    ver_a = client.post("/api/auth/verify", json={"identifier": "user_a@test.com", "code": "927824"})
    token_a = ver_a.json()["access_token"]
    user_a_id = ver_a.json()["user"]["id"]
    headers_a = {"Authorization": f"Bearer {token_a}"}

    # Create User B
    reg_b = client.post("/api/auth/register", json={"identifier": "user_b@test.com", "password": "PasswordUserB1!"})
    ver_b = client.post("/api/auth/verify", json={"identifier": "user_b@test.com", "code": "927824"})
    token_b = ver_b.json()["access_token"]
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # Create document owned by User A
    doc_a = DocumentExtraction(
        file_name="invoice_user_a.pdf",
        file_hash="hash_user_a_123",
        owner_user_id=user_a_id,
        vendor_name=ExtractedField(value="Vendor Alpha", confidence=0.95),
        invoice_id=ExtractedField(value="INV-ALPHA-01", confidence=0.99),
        total=ExtractedField(value=5000.0, confidence=0.99),
        created_at="2026-09-01T10:00:00Z",
    )
    doc_a_id = save_document(doc_a, owner_user_id=user_a_id)

    # 1. User A can retrieve doc_a
    res_a = client.get(f"/api/audit/documents/{doc_a_id}", headers=headers_a)
    assert res_a.status_code == 200
    assert res_a.json()["vendor_name"]["value"] == "Vendor Alpha"

    # 2. User B CANNOT retrieve doc_a (Strict Data Isolation)
    res_b = client.get(f"/api/audit/documents/{doc_a_id}", headers=headers_b)
    assert res_b.status_code == 404

    # 3. User B's list does not include doc_a
    list_b = client.get("/api/audit/documents", headers=headers_b)
    assert list_b.status_code == 200
    assert len(list_b.json()) == 0

    # 4. User B cannot review doc_a
    rev_b = client.patch(
        f"/api/audit/documents/{doc_a_id}/review",
        headers=headers_b,
        json={"manual_review_status": "approved", "notes": "Unauthorized review attempt"},
    )
    assert rev_b.status_code == 404

    # 5. User B cannot delete doc_a
    del_b = client.delete(f"/api/audit/documents/{doc_a_id}", headers=headers_b)
    assert del_b.status_code == 404


def test_destructive_operations_reset_and_delete_account():
    # Register User C
    reg_c = client.post("/api/auth/register", json={"identifier": "user_c@test.com", "password": "PasswordUserC1!"})
    ver_c = client.post("/api/auth/verify", json={"identifier": "user_c@test.com", "code": "927824"})
    token_c = ver_c.json()["access_token"]
    user_c_id = ver_c.json()["user"]["id"]
    headers_c = {"Authorization": f"Bearer {token_c}"}

    # Create 2 documents for User C
    for i in range(2):
        doc = DocumentExtraction(
            file_name=f"invoice_c_{i}.pdf",
            file_hash=f"hash_c_{i}",
            owner_user_id=user_c_id,
            vendor_name=ExtractedField(value=f"Vendor C{i}", confidence=0.9),
            invoice_id=ExtractedField(value=f"INV-C-{i}", confidence=0.9),
            total=ExtractedField(value=100.0 * (i + 1), confidence=0.9),
            created_at="2026-09-01T10:00:00Z",
        )
        save_document(doc, owner_user_id=user_c_id)

    # Verify User C has 2 docs
    list_c = client.get("/api/audit/documents", headers=headers_c)
    assert len(list_c.json()) == 2

    # 1. Reset My Data without correct phrase fails
    reset_fail_phrase = client.post(
        "/api/users/reset-data",
        headers=headers_c,
        json={"password": "PasswordUserC1!", "confirmation_phrase": "WRONG"},
    )
    assert reset_fail_phrase.status_code == 422 or reset_fail_phrase.status_code == 400

    # 2. Reset My Data with wrong password fails
    reset_fail_pwd = client.post(
        "/api/users/reset-data",
        headers=headers_c,
        json={"password": "WrongPassword!", "confirmation_phrase": "RESET"},
    )
    assert reset_fail_pwd.status_code == 401

    # 3. Reset My Data with valid credentials succeeds
    reset_ok = client.post(
        "/api/users/reset-data",
        headers=headers_c,
        json={"password": "PasswordUserC1!", "confirmation_phrase": "RESET"},
    )
    assert reset_ok.status_code == 200
    assert reset_ok.json()["deleted_documents"] == 2

    # Docs are wiped for User C
    list_after_reset = client.get("/api/audit/documents", headers=headers_c)
    assert len(list_after_reset.json()) == 0

    # User account is still intact
    me_res = client.get("/api/auth/me", headers=headers_c)
    assert me_res.status_code == 200

    # 4. Delete Account
    del_acc = client.request(
        "DELETE",
        "/api/users/account",
        headers=headers_c,
        json={"password": "PasswordUserC1!", "confirmation_phrase": "DELETE"},
    )
    assert del_acc.status_code == 200

    # Post-delete session is invalid
    me_after_del = client.get("/api/auth/me", headers=headers_c)
    assert me_after_del.status_code == 401


def test_document_file_retrieval_and_bulk_deletion():
    from app.services.storage import storage_service

    # Register User D
    reg_d = client.post("/api/auth/register", json={"identifier": "user_d@test.com", "password": "PasswordUserD1!"})
    ver_d = client.post("/api/auth/verify", json={"identifier": "user_d@test.com", "code": "927824"})
    token_d = ver_d.json()["access_token"]
    user_d_id = ver_d.json()["user"]["id"]
    headers_d = {"Authorization": f"Bearer {token_d}"}

    # Store 2 files in persistent storage and database
    mock_pdf_bytes = b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\nxref\n0 2\n0000000000 65535 f \n0000000009 00000 n \ntrailer<</Size 2/Root 1 0 R>>\nstartxref\n50\n%%EOF"
    key1, hash1, size1, ctype1 = storage_service.save_file(user_d_id, "invoice_d1.pdf", mock_pdf_bytes)
    key2, hash2, size2, ctype2 = storage_service.save_file(user_d_id, "invoice_d2.pdf", mock_pdf_bytes)

    doc1 = DocumentExtraction(
        file_name="invoice_d1.pdf",
        file_hash=hash1,
        storage_key=key1,
        content_type=ctype1,
        file_size=size1,
        owner_user_id=user_d_id,
        vendor_name=ExtractedField(value="Vendor D1", confidence=0.95),
        invoice_id=ExtractedField(value="INV-D1", confidence=0.95),
        total=ExtractedField(value=250.0, confidence=0.95),
        created_at="2026-09-01T10:00:00Z",
    )
    doc1_id = save_document(doc1, owner_user_id=user_d_id)

    doc2 = DocumentExtraction(
        file_name="invoice_d2.pdf",
        file_hash=hash2,
        storage_key=key2,
        content_type=ctype2,
        file_size=size2,
        owner_user_id=user_d_id,
        vendor_name=ExtractedField(value="Vendor D2", confidence=0.95),
        invoice_id=ExtractedField(value="INV-D2", confidence=0.95),
        total=ExtractedField(value=350.0, confidence=0.95),
        created_at="2026-09-01T10:00:00Z",
    )
    doc2_id = save_document(doc2, owner_user_id=user_d_id)

    # List documents
    docs = client.get("/api/audit/documents", headers=headers_d).json()
    assert len(docs) == 2

    # Test file retrieval endpoint
    file_res = client.get(f"/api/audit/documents/{doc1_id}/file", headers=headers_d)
    assert file_res.status_code == 200
    assert "application/pdf" in file_res.headers.get("content-type", "")
    assert file_res.content == mock_pdf_bytes

    # Test bulk delete
    bulk_res = client.post(
        "/api/audit/documents/bulk-delete",
        headers=headers_d,
        json={"document_ids": [doc1_id, doc2_id]},
    )
    assert bulk_res.status_code == 200
    assert bulk_res.json()["deleted_count"] == 2

    # Documents list is now empty
    docs_after = client.get("/api/audit/documents", headers=headers_d).json()
    assert len(docs_after) == 0

    # Physical file is also deleted
    file_after = storage_service.get_file(user_d_id, key1)
    assert file_after is None


def test_unauthenticated_requests_strictly_rejected_401():
    """Verify that unauthenticated requests to document endpoints return 401 without leakage."""
    # 1. /api/audit/documents
    res1 = client.get("/api/audit/documents")
    assert res1.status_code == 401
    assert "authentication required" in res1.json()["detail"].lower()

    # 2. /api/audit/summary
    res2 = client.get("/api/audit/summary")
    assert res2.status_code == 401

    # 3. /api/audit/documents/bulk-delete
    res3 = client.post("/api/audit/documents/bulk-delete", json={"document_ids": []})
    assert res3.status_code == 401

    # 4. Bad/expired token
    res4 = client.get("/api/audit/documents", headers={"Authorization": "Bearer invalid_nonexistent_token"})
    assert res4.status_code == 401


def test_cookie_based_authentication():
    """Verify that HttpOnly session cookie 'fee_auditor_session' authenticates requests."""
    reg = client.post("/api/auth/register", json={"identifier": "cookie_user@test.com", "password": "CookiePassword123!"})
    ver = client.post("/api/auth/verify", json={"identifier": "cookie_user@test.com", "code": "927824"})
    token = ver.json()["access_token"]
    user_id = ver.json()["user"]["id"]

    # Ingest document
    doc = DocumentExtraction(
        file_name="cookie_doc.pdf",
        file_hash="hash_cookie_123",
        owner_user_id=user_id,
        vendor_name=ExtractedField(value="Cookie Vendor", confidence=0.9),
        invoice_id=ExtractedField(value="INV-CK-01", confidence=0.9),
        total=ExtractedField(value=999.0, confidence=0.95),
        created_at="2026-09-01T10:00:00Z",
    )
    save_document(doc, owner_user_id=user_id)

    # Use cookie instead of Authorization header
    client.cookies.set("fee_auditor_session", token)
    res = client.get("/api/audit/documents")
    assert res.status_code == 200
    docs = res.json()
    assert len(docs) == 1
    assert docs[0]["vendor_name"]["value"] == "Cookie Vendor"

    # Logout revokes cookie
    logout_res = client.post("/api/auth/logout")
    assert logout_res.status_code == 200

    # Post-logout request with old cookie fails
    res_after = client.get("/api/audit/documents")
    assert res_after.status_code == 401
    client.cookies.clear()


def test_relational_schema_and_authoritative_dashboard_summary():
    """Verify extractions, audit_runs, validation_flags, review_actions tables and summary metrics."""
    from app.db.session import get_db_connection
    from app.db.repository import update_manual_review, get_dashboard_summary

    reg = client.post("/api/auth/register", json={"identifier": "relational@test.com", "password": "Relational123!"})
    ver = client.post("/api/auth/verify", json={"identifier": "relational@test.com", "code": "927824"})
    token = ver.json()["access_token"]
    user_id = ver.json()["user"]["id"]
    headers = {"Authorization": f"Bearer {token}"}

    # Save clean document
    doc_clean = DocumentExtraction(
        file_name="clean_doc.pdf",
        file_hash="hash_clean_rel",
        owner_user_id=user_id,
        vendor_name=ExtractedField(value="Clean Vendor", confidence=0.95),
        invoice_id=ExtractedField(value="INV-CLEAN-01", confidence=0.95),
        total=ExtractedField(value=1000.0, confidence=0.95),
        audit_status="clean",
        created_at="2026-09-01T10:00:00Z",
    )
    save_document(doc_clean, owner_user_id=user_id)

    # Save flagged document with V01 flag
    doc_flagged = DocumentExtraction(
        file_name="flagged_doc.pdf",
        file_hash="hash_flag_rel",
        owner_user_id=user_id,
        vendor_name=ExtractedField(value="Flagged Vendor", confidence=0.95),
        invoice_id=ExtractedField(value="INV-FLAG-01", confidence=0.95),
        total=ExtractedField(value=2000.0, confidence=0.95),
        audit_status="flagged",
        validation_flags=[
            ValidationFlag(
                rule_id="V01",
                rule_name="Total Mismatch",
                severity="CRITICAL",
                field_name="total",
                reason="Calculated sum != total",
                expected_value="1900.00",
                actual_value="2000.00",
            )
        ],
        created_at="2026-09-02T10:00:00Z",
    )
    flagged_id = save_document(doc_flagged, owner_user_id=user_id)

    # Verify relational entities exist in database
    with get_db_connection() as conn:
        cursor = conn.cursor()
        # 1. extractions table
        cursor.execute("SELECT * FROM extractions WHERE document_id = ?;", (flagged_id,))
        ext = cursor.fetchone()
        assert ext is not None
        assert "Flagged Vendor" in ext["extracted_fields"]

        # 2. audit_runs table
        cursor.execute("SELECT * FROM audit_runs WHERE document_id = ?;", (flagged_id,))
        run = cursor.fetchone()
        assert run is not None
        assert run["audit_status"] == "flagged"

        # 3. validation_flags table
        cursor.execute("SELECT * FROM validation_flags WHERE document_id = ?;", (flagged_id,))
        flags = cursor.fetchall()
        assert len(flags) == 1
        assert flags[0]["rule_id"] == "V01"

    # Review flagged document
    update_manual_review(flagged_id, status="approved", notes="Manually approved variance", owner_user_id=user_id)

    with get_db_connection() as conn:
        cursor = conn.cursor()
        # 4. review_actions table
        cursor.execute("SELECT * FROM review_actions WHERE document_id = ?;", (flagged_id,))
        actions = cursor.fetchall()
        assert len(actions) == 1
        assert actions[0]["decision"] == "approved"
        assert actions[0]["reviewer_user_id"] == user_id

    # Verify DashboardSummary API response
    summary_res = client.get("/api/audit/summary", headers=headers)
    assert summary_res.status_code == 200
    s_data = summary_res.json()
    assert s_data["total_documents"] == 2
    assert s_data["clean_documents"] == 1
    assert s_data["total_value"] == 3000.0
    assert s_data["v01_count"] == 1
    assert s_data["v02_count"] == 0
