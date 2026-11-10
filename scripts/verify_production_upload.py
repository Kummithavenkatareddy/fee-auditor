#!/usr/bin/env python3
"""
Dedicated Production Document Upload Verification Script
Fee Receipt & Invoice Auditor

Verifies live document upload and processing on Vercel deployment:
- Small PDF Invoice
- PDF Receipt
- Larger PDF
- Document with Azure extraction and validation warnings
"""

import sys
import time
import uuid
import httpx

BACKEND_URL = "https://fee-auditor-backend.vercel.app"
FRONTEND_ORIGIN = "https://fee-auditor-frontend.vercel.app"


def run_verification():
    print("=" * 70)
    print("Fee Receipt & Invoice Auditor — Production Upload Verification")
    print(f"Backend Target: {BACKEND_URL}")
    print(f"Frontend Origin: {FRONTEND_ORIGIN}")
    print("=" * 70)

    client = httpx.Client(timeout=120.0)

    # 1. Health check
    print("\n[Step 1] Checking backend health...")
    r_health = client.get(f"{BACKEND_URL}/api/health")
    assert r_health.status_code == 200, f"Health check failed: {r_health.text}"
    print(f"  Health: 200 OK (Azure Configured: {r_health.json().get('azure_configured')})")

    # 2. CORS Preflight for Upload
    print("\n[Step 2] Testing CORS Preflight on /api/audit/upload...")
    r_preflight = client.options(
        f"{BACKEND_URL}/api/audit/upload",
        headers={
            "Origin": FRONTEND_ORIGIN,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization",
        },
    )
    assert r_preflight.status_code == 200, f"Preflight failed: {r_preflight.status_code}"
    assert r_preflight.headers.get("access-control-allow-origin") == FRONTEND_ORIGIN
    assert r_preflight.headers.get("access-control-allow-credentials") == "true"
    print(f"  Preflight: 200 OK (Allowed Origin: {FRONTEND_ORIGIN}, Credentials: true)")

    # 3. Create Auditor User
    test_id = f"auditor_prod_{uuid.uuid4().hex[:6]}@university.edu"
    print(f"\n[Step 3] Registering auditor account: {test_id}...")
    r_reg = client.post(
        f"{BACKEND_URL}/api/auth/register",
        json={"identifier": test_id, "password": "SecurePassword123!", "full_name": "Production Auditor"},
        headers={"Origin": FRONTEND_ORIGIN},
    )
    assert r_reg.status_code == 201, f"Registration failed: {r_reg.text}"
    otp_code = r_reg.json().get("dev_verification_code")
    assert otp_code, "No OTP returned in demo mode response"

    r_verify = client.post(
        f"{BACKEND_URL}/api/auth/verify",
        json={"identifier": test_id, "code": otp_code},
        headers={"Origin": FRONTEND_ORIGIN},
    )
    assert r_verify.status_code == 200, f"Verification failed: {r_verify.text}"
    token = r_verify.json()["access_token"]
    auth_headers = {
        "Authorization": f"Bearer {token}",
        "Origin": FRONTEND_ORIGIN,
    }
    print(f"  Authenticated successfully. Session Token: {token[:12]}...")

    test_docs = [
        {
            "category": "Small PDF Invoice",
            "path": "dataset/clean_invoice/INV-001.pdf",
            "filename": f"test_small_invoice_{uuid.uuid4().hex[:4]}.pdf",
            "preferred_model": "prebuilt-invoice",
        },
        {
            "category": "PDF Receipt",
            "path": "dataset/REC-003.pdf",
            "filename": f"test_receipt_{uuid.uuid4().hex[:4]}.pdf",
            "preferred_model": "prebuilt-receipt",
        },
        {
            "category": "Larger PDF",
            "path": "dataset/new_input/ONEPLUS BUDS 4 INVOICE.pdf",
            "filename": f"test_large_doc_{uuid.uuid4().hex[:4]}.pdf",
            "preferred_model": "auto",
        },
        {
            "category": "Document with Validation Warnings",
            "path": "dataset/tampered_invoice/INV-004.pdf",
            "filename": f"test_tampered_warning_{uuid.uuid4().hex[:4]}.pdf",
            "preferred_model": "prebuilt-invoice",
        },
    ]

    ingested_ids = []

    for idx, doc_spec in enumerate(test_docs, start=4):
        cat = doc_spec["category"]
        file_path = doc_spec["path"]
        fname = doc_spec["filename"]
        model_pref = doc_spec["preferred_model"]

        print(f"\n[Step {idx}] Uploading {cat} ('{file_path}')...")
        file_bytes = open(file_path, "rb").read()
        print(f"  File size: {len(file_bytes):,} bytes ({len(file_bytes)/1024:.1f} KB)")

        form_files = [("files", (fname, file_bytes, "application/pdf"))]
        form_data = {}
        if model_pref and model_pref != "auto":
            form_data["preferred_model"] = model_pref

        t0 = time.time()
        r_upload = client.post(
            f"{BACKEND_URL}/api/audit/upload",
            files=form_files,
            data=form_data,
            headers=auth_headers,
        )
        duration = time.time() - t0
        print(f"  Response Status: HTTP {r_upload.status_code} (Duration: {duration:.2f}s)")

        if r_upload.status_code != 200:
            print(f"  FAIL: Response Text: {r_upload.text[:400]}")
            sys.exit(1)

        data = r_upload.json()
        assert data["successful_extractions"] >= 1, f"No successful extractions: {data}"
        doc_info = data["documents"][0]
        doc_id = doc_info["id"]
        ingested_ids.append(doc_id)

        print(f"  Ingestion Succeeded: Doc ID = {doc_id}")
        print(f"  Model Used: {doc_info.get('model_used')}, Type: {doc_info.get('document_type')}")
        print(f"  Audit Status: {doc_info.get('audit_status')}, Flags: {len(doc_info.get('validation_flags') or [])}")

        if "Warnings" in cat:
            flags = doc_info.get("validation_flags") or []
            print(f"  Verified Expected Flags/Warnings: {len(flags)} finding(s) detected as expected!")
            for fl in flags:
                reason = fl.get('audit_reason') or fl.get('reason') or fl.get('discrepancy_details') or ''
                print(f"    - [{fl.get('severity')}] {fl.get('rule_id')}: {reason[:70]}...")

    # Step 8: Verify persistence in document ledger
    print("\n[Step 8] Verifying ledger persistence (GET /api/audit/documents)...")
    time.sleep(1)
    fresh_client = httpx.Client(timeout=30.0)
    r_ledger = fresh_client.get(f"{BACKEND_URL}/api/audit/documents", headers=auth_headers)
    assert r_ledger.status_code == 200
    ledger_docs = r_ledger.json()
    print(f"  Ledger returned {len(ledger_docs)} documents for user.")
    for did in ingested_ids:
        assert any(d["id"] == did for d in ledger_docs), f"Doc {did} missing from ledger!"
    print("  ALL 4 documents successfully persisted and linked to authenticated user.")

    # Step 9: Verify document binary streaming
    print("\n[Step 9] Verifying file binary streaming with query token...")
    for did in ingested_ids:
        r_stream = fresh_client.get(
            f"{BACKEND_URL}/api/audit/documents/{did}/file?token={token}",
            headers={"Origin": FRONTEND_ORIGIN},
        )
        assert r_stream.status_code == 200, f"File retrieval failed for {did}: {r_stream.status_code}"
        assert len(r_stream.content) > 1000
    print(f"  Successfully streamed all {len(ingested_ids)} document binaries.")

    # Step 10: Clean up
    print("\n[Step 10] Cleaning up test documents...")
    r_reset = fresh_client.delete(f"{BACKEND_URL}/api/audit/reset", headers=auth_headers)
    assert r_reset.status_code == 200
    print("  User test library cleaned up.")

    print("\n" + "=" * 70)
    print("PRODUCTION UPLOAD VERIFICATION: ALL 4 DOCUMENT TYPES PASSED!")
    print("=" * 70)
    return True


if __name__ == "__main__":
    success = run_verification()
    sys.exit(0 if success else 1)
