# P05 — Remediation and Regression Hardening Report

**Project**: P05 — Fee Receipt and Invoice Auditor  
**Audit Reference**: [P05_REQUIREMENTS_AUDIT.md](file:///c:/Users/kvred/projects/fee-auditor/P05_REQUIREMENTS_AUDIT.md)  
**Date**: November 9, 2026  
**Auditor Roles**: Senior Software Architect, Azure AI Engineer, QA Automation Engineer, Application Security Reviewer  
**Status**: **100% REMEDIATED & REGRESSION HARDENED**

---

## 1. Executive Summary

A comprehensive remediation and regression hardening initiative was executed across the backend, frontend, Azure Document Intelligence integration, test harnesses, and synthetic dataset pipelines. All 6 partial compliance items identified in `P05_REQUIREMENTS_AUDIT.md` have been fully resolved.

| Audit Area | Pre-Remediation Status | Post-Remediation Status | Defects Resolved |
| :--- | :---: | :---: | :--- |
| **Model Routing** | PARTIAL | **PASS (100%)** | Filename prefix regex routing (`REC-`, `rec_`, `receipt`), precedence hierarchy |
| **Date Parsing** | PARTIAL | **PASS (100%)** | 8 deterministic date formats, inclusive academic term bounds |
| **Dataset Unification** | PARTIAL | **PASS (100%)** | Standardized 6 canonical INR PDFs, archived USD legacy, unified ground truth |
| **OCR Confidence** | PASS | **PASS (100%)** | Retained original confidences, boundary tests (<0.85, ==0.85, >0.85) |
| **Security Hardening** | PARTIAL | **PASS (100%)** | 20 MB streaming upload limit, explicit whitelist CORS configuration |
| **Endpoint Normalization** | PARTIAL | **PASS (100%)** | Trailing slash removal, credential leakage prevention |
| **UI Formatting** | PARTIAL | **PASS (100%)** | Unified Indian Rupee (`₹`) formatting in tables and summary cards |
| **Automated Tests** | 42 passing | **73 passing (Backend) + 14 passing (Frontend)** | Zero regressions, 31 new dedicated remediation tests |

---

## 2. Remediated Defects & Implementation Details

### Task 1 — Receipt Model Routing
- **Problem**: In [extractor.py](file:///c:/Users/kvred/projects/fee-auditor/backend/app/services/extractor.py), automatic model selection only checked `"receipt" in lower_name`. Standard receipt filenames like `REC-003.pdf` or `REC_006.pdf` defaulted to `prebuilt-invoice`, causing false V02 (Missing Tax Number) flags.
- **Resolution**:
  - Implemented `is_receipt_filename(filename: str) -> bool` recognizing `receipt`, `REC-`, `REC_`, `rec-`, and `rec_` tokens.
  - Implemented `determine_model(filename, preferred_model, document_type) -> str` enforcing a strict precedence hierarchy:
    1. Explicit `preferred_model` (`prebuilt-receipt` or `prebuilt-invoice`)
    2. Explicit `document_type` (`receipt` or `invoice`)
    3. Filename heuristics (`is_receipt_filename`)
    4. Fallback default (`prebuilt-invoice`)
  - Updated `analyze_receipt_result()` to fall back to `Subtotal` or regex on `result.content` when `Total` is absent on educational fee receipts, and fall back to regex on `result.content` for `ReceiptId` / `TransactionId`.
- **Files Modified**:
  - [backend/app/services/extractor.py](file:///c:/Users/kvred/projects/fee-auditor/backend/app/services/extractor.py)
  - [backend/app/services/__init__.py](file:///c:/Users/kvred/projects/fee-auditor/backend/app/services/__init__.py)

---

### Task 2 — Deterministic Date Parsing & Inclusive Term Validation
- **Problem**: `_parse_iso_date()` in [validator.py](file:///c:/Users/kvred/projects/fee-auditor/backend/app/services/validator.py) only supported numeric date formats, failing on natural date representations returned by OCR (such as `'15 November 2026'`).
- **Resolution**:
  - Implemented deterministic parsing across 8 required calendar date formats:
    - `YYYY-MM-DD` (ISO)
    - `DD/MM/YYYY`
    - `MM/DD/YYYY`
    - `DD-MM-YYYY`
    - `DD Month YYYY` (e.g. `15 November 2026`)
    - `DD Mon YYYY` (e.g. `15 Nov 2026`)
    - `Month DD, YYYY` (e.g. `November 15, 2026`)
    - `Mon DD, YYYY` (e.g. `Nov 15, 2026`)
    - Variations: `YYYY/MM/DD`, `MM-DD-YYYY`, and formats without commas.
  - Extended `_extract_date_value()` in [extractor.py](file:///c:/Users/kvred/projects/fee-auditor/backend/app/services/extractor.py) to normalize natural language date strings to ISO `YYYY-MM-DD`.
  - Verified inclusive academic term bounds (`2026-08-01` to `2026-12-31`): both boundary dates pass without violation.
- **Files Modified**:
  - [backend/app/services/validator.py](file:///c:/Users/kvred/projects/fee-auditor/backend/app/services/validator.py)
  - [backend/app/services/extractor.py](file:///c:/Users/kvred/projects/fee-auditor/backend/app/services/extractor.py)

---

### Task 3 — Unified Synthetic Dataset (INR Financial Documents)
- **Problem**: The workspace had competing active sample directories: `backend/synthetic_data/samples/` contained 6 USD PDFs (`clean_tuition_invoice_1.pdf`, etc.), while `dataset/` contained 6 Indian INR PDFs (`INV-001.pdf` to `REC-006.pdf`). The `/load-samples` endpoint loaded USD documents while UI displays used `₹`.
- **Resolution**:
  - Safely archived legacy USD PDFs to `backend/synthetic_data/samples_usd_legacy/`.
  - Standardized `backend/synthetic_data/samples/` to contain exclusively the 6 canonical INR PDFs:
    1. `INV-001.pdf`: Clean Vendor Invoice (Aster Office Supplies Pvt. Ltd., ₹9,794.00, GSTIN: `FAKE-GST-000001`)
    2. `INV-002.pdf`: Clean Vendor Invoice (BluePeak IT Solutions, ₹8,850.00, GSTIN: `FAKE-GST-000002`)
    3. `REC-003.pdf`: Clean Educational Fee Receipt (Greenfield Technical Institute, ₹29,000.00, GST exempt)
    4. `INV-004.pdf`: Tampered Total Mismatch (Crestline Equipment, ₹55,920.00 printed vs ₹51,920.00 expected; discrepancy: ₹4,000.00)
    5. `INV-005.pdf`: Missing Tax Number (Meridian Educational Technologies, GSTIN omitted)
    6. `REC-006.pdf`: Outside Academic Term (Greenfield Technical Institute, date `2027-01-15` outside Fall 2026 term)
  - Updated [backend/synthetic_data/ground_truth.json](file:///c:/Users/kvred/projects/fee-auditor/backend/synthetic_data/ground_truth.json) with dual lookup (document metadata list and filename dictionary).
  - Fixed hardcoded `$` in [DocumentsTable.jsx](file:///c:/Users/kvred/projects/fee-auditor/frontend/src/components/DocumentsTable.jsx#L120) and [SummaryCards.jsx](file:///c:/Users/kvred/projects/fee-auditor/frontend/src/components/SummaryCards.jsx#L57) to render `₹` formatted with `'en-IN'`.
- **Files Modified**:
  - `backend/synthetic_data/samples/` (canonical INR PDFs)
  - `backend/synthetic_data/samples_usd_legacy/` (archived USD PDFs)
  - [backend/synthetic_data/ground_truth.json](file:///c:/Users/kvred/projects/fee-auditor/backend/synthetic_data/ground_truth.json)
  - [frontend/src/components/DocumentsTable.jsx](file:///c:/Users/kvred/projects/fee-auditor/frontend/src/components/DocumentsTable.jsx)
  - [frontend/src/components/SummaryCards.jsx](file:///c:/Users/kvred/projects/fee-auditor/frontend/src/components/SummaryCards.jsx)

---

### Task 4 — OCR Confidence Handling
- **Problem**: Need to verify live Azure confidence preservation without altering scores or lowering the 0.85 threshold.
- **Resolution**:
  - Verified that all extracted fields preserve their original Azure confidence scores (0.0 to 1.0) without modification.
  - Ensured fields with status `MISSING` or `NOT_APPLICABLE` (such as Tax ID on receipts) never trigger V05 warnings.
  - Added explicit plain-language recommendations to V05 flag reasons: `"Extraction confidence for {field_label} is {conf:.1%}, which is below the required accuracy threshold of {conf_thresh:.1%}. Manual verification recommended."`.
  - Added unit tests for `< 0.85`, `== 0.85`, and `> 0.85` thresholds.
- **Files Modified**:
  - [backend/app/services/validator.py](file:///c:/Users/kvred/projects/fee-auditor/backend/app/services/validator.py)
  - [backend/tests/test_remediation.py](file:///c:/Users/kvred/projects/fee-auditor/backend/tests/test_remediation.py)

---

### Task 5 — Security Hardening
- **Problem**:
  1. No upload file size limit was enforced before buffering into memory.
  2. [backend/app/main.py](file:///c:/Users/kvred/projects/fee-auditor/backend/app/main.py) used `allow_origins=["*"]` with `allow_credentials=True`.
- **Resolution**:
  - Added `MAX_UPLOAD_SIZE_MB = 20` and `CORS_ORIGINS` to [backend/app/config.py](file:///c:/Users/kvred/projects/fee-auditor/backend/app/config.py).
  - In [backend/app/routers/audit.py](file:///c:/Users/kvred/projects/fee-auditor/backend/app/routers/audit.py):
    - Added immediate size check via `file.size` if reported by headers.
    - Implemented chunked 1 MB stream reading to reject oversized files before buffering the full payload into memory.
    - Returns structured error: `"File exceeds maximum allowed upload size of 20 MB."`.
  - In [backend/app/main.py](file:///c:/Users/kvred/projects/fee-auditor/backend/app/main.py):
    - Configured CORS with `allow_origins=settings.cors_origins_list` (restricting to `http://localhost:5173`, `http://127.0.0.1:5173`, `http://localhost:3000`).
    - Disallowed wildcard origins with credentials.
- **Files Modified**:
  - [backend/app/config.py](file:///c:/Users/kvred/projects/fee-auditor/backend/app/config.py)
  - [backend/app/main.py](file:///c:/Users/kvred/projects/fee-auditor/backend/app/main.py)
  - [backend/app/routers/audit.py](file:///c:/Users/kvred/projects/fee-auditor/backend/app/routers/audit.py)

---

### Task 6 — Azure Endpoint Normalization
- **Problem**: Trailing slashes on `AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT` could produce malformed double-slash URLs when constructing REST requests.
- **Resolution**:
  - Added `@property def canonical_azure_endpoint` in `Settings` that automatically strips whitespace and trailing slashes.
  - Used `settings.canonical_azure_endpoint` in [azure_client.py](file:///c:/Users/kvred/projects/fee-auditor/backend/app/services/azure_client.py).
  - Verified credentials and API keys are never written to logs or error outputs.
- **Files Modified**:
  - [backend/app/config.py](file:///c:/Users/kvred/projects/fee-auditor/backend/app/config.py)
  - [backend/app/services/azure_client.py](file:///c:/Users/kvred/projects/fee-auditor/backend/app/services/azure_client.py)

---

## 3. Test Execution Proof

### Backend Test Suite (pytest)
```bash
python -m pytest backend/tests -v
```
**Result**: **73 passed in 87.46s**
- `backend/tests/test_api.py`: 2 passed
- `backend/tests/test_audit_milestone6.py`: 3 passed (A1, A2, A3 live Azure acceptance)
- `backend/tests/test_azure_integration.py`: 4 passed (live Azure connection, hash, invoice & receipt extraction)
- `backend/tests/test_milestone1_foundation.py`: 5 passed
- `backend/tests/test_milestone2_azure_mocked.py`: 9 passed
- `backend/tests/test_milestone3_backend.py`: 12 passed
- `backend/tests/test_remediation.py`: 31 passed (Dedicated remediation test suite)
- `backend/tests/test_validator.py`: 7 passed

### Frontend Test Suite (vitest)
```bash
npm --prefix frontend test -- --run
```
**Result**: **14 passed in 2.55s**
- `ConfidenceBadge` rendering: 5 tests passed
- `StatusBadge` rendering: 3 tests passed
- `SeverityBadge` rendering: 4 tests passed
- `Currency and Metric Consistency`: 2 tests passed (`SummaryCards` with `₹`, `DocumentsTable` with `₹`)

---

## 4. Acceptance Criteria Verification (A1, A2, A3)

Executed via live Azure AI Document Intelligence end-to-end integration:

### Demonstration A1 — Clean Document Extraction
- **Target**: `REC-003.pdf` & `INV-001.pdf`
- **Model Used**: `prebuilt-receipt` for `REC-003.pdf`, `prebuilt-invoice` for `INV-001.pdf`
- **Extracted Fields (`REC-003.pdf`)**:
  - Vendor/Institution: `GREENFIELD TECHNICAL INSTITUTE` (Confidence: 0.955)
  - Date: `2026-11-15` (Confidence: 0.994)
  - Total: `₹29,000.00` (Confidence: 0.995)
  - Tax ID: `NOT_APPLICABLE`
  - Line Items: 3 items totaling ₹29,000.00
  - Validation Flags: 0 flags
  - **Audit Status**: **`CLEAN`** (100% compliant)
- **Extracted Fields (`INV-001.pdf`)**:
  - Vendor: `Aster Office Supplies Pvt. Ltd.` (Confidence: 0.885)
  - Date: `2026-09-12` (Confidence: 0.926)
  - Total: `₹9,794.00` (Confidence: 0.939)
  - Line Items: 3 items (Sum ₹8,300.00 + GST ₹1,494.00 = ₹9,794.00)
  - V01 Financial Flags: 0 flags

### Demonstration A2 — Tampered & Defective Document Detection
- **A2.1 (Total Mismatch — V01)**:
  - Document: `INV-004.pdf`
  - Discrepancy: `₹4,000.00`
  - Stated Total: `₹55,920.00`
  - Reconciled Total: `₹51,920.00` (Subtotal ₹44,000.00 + Tax ₹7,920.00)
  - Flag: `FLAG V01 — TOTAL MISMATCH` (`CRITICAL`)
  - Reason: Plain-language discrepancy explanation with exact expected vs stated figures.
- **A2.2 (Missing Vendor Tax Number — V02)**:
  - Document: `INV-005.pdf`
  - Flag: `FLAG V02 — MISSING TAX NUMBER` (`MEDIUM`)
  - Reason: Plain-language warning identifying absent tax registration on a vendor invoice.
- **A2.3 (Outside Academic Term — V04)**:
  - Document: `REC-006.pdf`
  - Date: `2027-01-15`
  - Academic Term: `2026-08-01` to `2026-12-31`
  - Model: `prebuilt-receipt`
  - Flag: `FLAG V04 — OUTSIDE ACADEMIC TERM` (`MEDIUM`)
  - Reason: Date `2027-01-15` exceeds inclusive term boundary `2026-12-31`.

### Demonstration A3 — Duplicate Detection & Manual Review Highlighting
- **A3.1 (Duplicate Detection — V03)**:
  - Document: `INV-001.pdf` uploaded twice in succession.
  - Result: Second upload identified as `is_duplicate=True` and `is_exact_duplicate=True`.
  - Flag: `FLAG V03 — DUPLICATE DOCUMENT (EXACT FILE)` (`CRITICAL`).
  - Audit Trail: Original document `INV-001.pdf` and SHA-256 hash clearly identified in reason.
- **A3.2 (Confidence Highlighting — V05)**:
  - Synthetic identifier `FAKE-GST-000001` with Azure confidence `0.789` (< 0.85).
  - Flag: `FLAG V05 — LOW EXTRACTION CONFIDENCE` (`WARNING`).
  - Reason: `Extraction confidence for Vendor Tax ID is 78.9%, which is below the required accuracy threshold of 85.0%. Manual verification recommended.`
  - UI Highlighting: Yellow amber badge with manual review required.
- **A3.3 (CSV Export)**:
  - Endpoint `/api/audit/export/csv` generates structured CSV with headers: `Document ID`, `File Name`, `Vendor Name`, `Total Amount`, `Total Confidence`, `Tax ID Confidence`, `Flag Details`, `Manual Review Status`.

---

## 5. Artifact & File Change Summary

| File Path | Type | Nature of Modification |
| :--- | :--- | :--- |
| `backend/app/config.py` | Config | Added `CORS_ORIGINS`, `MAX_UPLOAD_SIZE_MB`, `canonical_azure_endpoint`, `max_upload_size_bytes` |
| `backend/app/main.py` | Backend | Replaced wildcard CORS with strict origin whitelist from settings |
| `backend/app/services/azure_client.py` | Service | Normalized endpoint with trailing slash removal |
| `backend/app/services/extractor.py` | Service | Added `is_receipt_filename`, `determine_model`, receipt fallback, natural date parsing |
| `backend/app/services/__init__.py` | Module | Exported `is_receipt_filename` and `determine_model` |
| `backend/app/services/validator.py` | Service | Added 8 date formats, inclusive term check, manual review notes on V05 |
| `backend/app/routers/audit.py` | Router | Added streaming 20 MB chunked file size limit and clear error rejection |
| `backend/synthetic_data/samples/` | Data | Standardized to 6 canonical INR PDFs (`INV-001` through `REC-006`) |
| `backend/synthetic_data/samples_usd_legacy/` | Data | Safely archived legacy USD PDFs |
| `backend/synthetic_data/ground_truth.json` | Data | Updated ground truth covering all 6 canonical INR documents |
| `frontend/src/components/DocumentsTable.jsx` | Frontend | Replaced hardcoded `$` with `₹` (formatted with `en-IN`) |
| `frontend/src/components/SummaryCards.jsx` | Frontend | Replaced hardcoded `$` with `₹` (formatted with `en-IN`) |
| `backend/tests/test_remediation.py` | Test | Added 31 dedicated unit tests for all remediation tasks |
| `backend/tests/test_audit_milestone6.py` | Test | Standardized acceptance tests to canonical INR documents |
| `backend/tests/test_milestone3_backend.py` | Test | Updated duplicate test path to canonical samples |
| `frontend/src/test/components.test.jsx` | Test | Added frontend test cases for `₹` currency rendering |
| `P05_REQUIREMENTS_AUDIT.md` | Doc | Updated audit document with post-remediation 100% PASS ratings |
| `P05_REMEDIATION_REPORT.md` | Doc | Comprehensive remediation and acceptance verification report |

---

## 6. Final Compliance Statement

The **P05 Fee Receipt and Invoice Auditor** is in full compliance with all architectural, security, algorithmic, and functional requirements. All validation decisions are performed in deterministic Python code without LLM hallucination risk, all Azure AI Document Intelligence models operate canonically, security controls enforce size and CORS restrictions, and the test suite passes with zero regressions.

