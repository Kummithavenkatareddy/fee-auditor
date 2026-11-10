# Fee Receipt & Invoice Auditor

A full-stack institutional audit platform for academic fee receipts and invoices (PDF, PNG, JPEG). It combines **Azure AI Content Safety** pre-screening, **Azure AI Document Intelligence** (`prebuilt-invoice` & `prebuilt-receipt`) extraction, and a deterministic Python rules engine (**V01–V05**) with GST-aware reconciliation and strict multi-user SQLite isolation.

---

## Quick Start

### 1. Prerequisites
- **Python 3.10+** (tested on Python 3.14)
- **Node.js 18+** & **npm**

### 2. Environment Configuration
Create a `.env` file in the project root (see `.env.example`):

```env
# Azure AI Document Intelligence
AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT=https://<your-doc-intel-resource>.cognitiveservices.azure.com/
AZURE_DOCUMENT_INTELLIGENCE_KEY=your_doc_intel_key_here
AZURE_API_VERSION=2024-11-30

# Azure AI Content Safety
CONTENT_SAFETY_ENDPOINT=https://<your-content-safety-resource>.cognitiveservices.azure.com/
CONTENT_SAFETY_KEY=your_content_safety_key_here
CONTENT_SAFETY_ENABLED=true
CONTENT_SAFETY_FAILURE_POLICY=fail_closed

# Academic Term Boundaries & SQLite
ACADEMIC_TERM_START=2026-08-01
ACADEMIC_TERM_END=2026-12-31
DATABASE_URL=sqlite:///./fee_auditor.db
BACKEND_PORT=8000
```

---

### 3. Run Backend

```powershell
# Install Python dependencies
pip install -r backend/requirements.txt

# Start FastAPI application
python -m uvicorn app.main:app --app-dir backend --reload --port 8000
```
- API Server: `http://localhost:8000`
- Interactive OpenAPI Docs: `http://localhost:8000/docs`

---

### 4. Run Frontend

```powershell
# Navigate to frontend and install dependencies
cd frontend
npm install

# Start Vite development server
npm run dev
```
- Dashboard UI: `http://localhost:5173`

---

## Core Capabilities

- **Azure AI Content Safety Pre-Screening**: Evaluates PDFs (embedded text & rendered page images) and image files before Document Intelligence extraction. Detects Sexual, Hate, Violence, Self-Harm, and custom blocklist terms under a fail-closed policy.
- **Financial Document Extraction**: Uses Azure AI Document Intelligence prebuilt models to extract vendor/merchant details, tax IDs, invoice numbers, line items, and multi-component taxes (CGST, SGST, IGST, Cess).
- **Deterministic Rules Engine (V01–V05)**:
  - **V01 (Total Mismatch)**: GST-aware reconciliation supporting tax-exclusive and tax-inclusive calculations.
  - **V02 (Missing Tax ID)**: Verifies presence of GSTIN, VAT, or EIN registration numbers.
  - **V03 (Duplicate Detection)**: Two-tier detection with Level 1 SHA-256 exact binary pre-check and Level 2 logical business key matching.
  - **V04 (Academic Term Compliance)**: Verifies invoice dates fall within the active academic semester.
  - **V05 (Confidence Verification)**: Highlights extracted fields scoring below 85% confidence.
- **Document Workspace**: Full-width split inspection layout with interactive PDF preview, field confidence indicators, manual review approval/rejection workflows, and Pandas-powered CSV export.
- **Multi-User Security & Isolation**: Session-based authentication with isolated document libraries, preventing cross-tenant data leakage.

---

## Running Tests

```powershell
# Run backend test suite (140 tests)
python -m pytest backend/tests -v

# Run frontend test suite (39 tests)
npm --prefix frontend test -- --run

# Production build check
npm --prefix frontend run build
```
