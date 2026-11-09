# Fee Receipt & Invoice Auditor

An enterprise-grade document intelligence and deterministic audit platform designed to ingest batches of academic fee receipts and invoices (PDF, PNG, JPEG), extract structured data via **Azure AI Document Intelligence** (`prebuilt-invoice` and `prebuilt-receipt` with API version `2024-11-30`), track field-level extraction confidence scores, persist records to SQLite, and execute strict deterministic Python compliance rules (V01–V05).

---

## 1. Technology Stack

- **Frontend**: React + Vite + Lucide Icons + Modern Responsive Dashboard
- **Backend**: Python 3.14 + FastAPI + Pydantic v2
- **Document Extraction**: Azure AI Document Intelligence SDK (`azure-ai-documentintelligence>=1.0.2`)
- **Azure Models**: `prebuilt-invoice` & `prebuilt-receipt` (API version: `2024-11-30`)
- **Database**: SQLite (ACID compliant with foreign keys & compound indexes)
- **CSV Export**: Pandas
- **Testing**: Pytest + FastAPI TestClient + ReportLab synthetic generator

---

## 2. Architecture & Data Flow

```
                      [ User Upload: PDF / PNG / JPEG (>= 5 documents) ]
                                             │
                                             ▼
                               ┌───────────────────────────┐
                               │     React + Vite UI       │
                               │  - Multi-file Dropzone    │
                               │  - Metric Summary Cards   │
                               │  - Confidence Badges      │
                               │  - Manual Review Drawer   │
                               │  - CSV Export Trigger     │
                               └─────────────┬─────────────┘
                                             │ HTTP POST /multipart
                                             ▼
                               ┌───────────────────────────┐
                               │      FastAPI Backend      │
                               │      (Port: 8000)         │
                               └─────────────┬─────────────┘
                                             │
                                             ▼
                       ┌───────────────────────────────────────────┐
                       │   Azure AI Document Intelligence Service  │
                       │   - Endpoint & Key Authentication         │
                       │   - prebuilt-invoice / prebuilt-receipt   │
                       │   - API version: 2024-11-30               │
                       └─────────────────────┬─────────────────────┘
                                             │
                                             ▼
                       ┌───────────────────────────────────────────┐
                       │       Normalization & Confidence          │
                       │   - Preserves per-field confidence score  │
                       │   - Computes SHA-256 file hash            │
                       └─────────────────────┬─────────────────────┘
                                             │
                                             ▼
                       ┌───────────────────────────────────────────┐
                       │    Deterministic Validation Rules Engine  │
                       │   (Strict Python Decimal Arithmetic)      │
                       │   - V01: Total Mismatch                   │
                       │   - V02: Missing Tax Number               │
                       │   - V03: Duplicate Invoice (Hash & ID)    │
                       │   - V04: Outside Academic Term            │
                       │   - V05: Low Confidence (< 0.85)          │
                       └─────────────────────┬─────────────────────┘
                                             │
                                             ▼
                       ┌───────────────────────────────────────────┐
                       │           SQLite Persistence              │
                       │   - documents, line_items, audit_flags    │
                       └─────────────────────┬─────────────────────┘
                                             │
                                             ▼
                       ┌───────────────────────────────────────────┐
                       │        Audit Results & CSV Export         │
                       │   - Pandas tabular export                 │
                       │   - Real-time dashboard updates           │
                       └───────────────────────────────────────────┘
```

---

## 3. Deterministic Validation Rules (Non-LLM)

| Rule ID | Rule Name | Description & Evaluation Logic | Severity |
| :--- | :--- | :--- | :--- |
| **V01** | **Total Mismatch** | Evaluates $\sum(\text{line\_items}) + \text{tax} - \text{discounts} \pm \text{adjustments}$ using exact Python `Decimal` arithmetic. Flags any absolute discrepancy $> \$0.02$. | `CRITICAL` |
| **V02** | **Missing Tax Number** | Flags documents lacking vendor tax registration identifiers (`EIN`, `VAT`, `GST`, or `Tax ID`). | `MEDIUM` |
| **V03** | **Duplicate Invoice** | Detects duplicate invoices across batch and historical records: 1) exact SHA-256 binary hash duplicates, 2) matching invoice numbers across separate files. | `CRITICAL` |
| **V04** | **Outside Academic Term** | Verifies that `invoice_date` strictly falls between `ACADEMIC_TERM_START` and `ACADEMIC_TERM_END` (configurable, default: 2026-08-01 to 2026-12-31). Flags out-of-term or unparsable dates. | `MEDIUM` |
| **V05** | **Low Confidence** | Evaluates Azure extraction confidence across required fields (`vendor_name`, `invoice_id`, `invoice_date`, `total`). Flags any field scoring below threshold (0.85). | `WARNING` |

---

## 4. Synthetic Test Dataset

The project contains a programmatic synthetic invoice generator located at [`backend/synthetic_data/generator.py`](file:///C:/Users/kvred/projects/fee-auditor/backend/synthetic_data/generator.py). It creates 6 distinct PDF documents with ground truth expectations stored in [`backend/synthetic_data/ground_truth.json`](file:///C:/Users/kvred/projects/fee-auditor/backend/synthetic_data/ground_truth.json):

1. **`clean_tuition_invoice_1.pdf`**: Clean tuition fee invoice ($1,500.00). Expects 0 flags.
2. **`clean_campus_store_receipt_2.pdf`**: Clean bookstore receipt ($216.00). Expects 0 flags.
3. **`clean_library_membership_invoice_3.pdf`**: Clean research library invoice ($472.50). Expects 0 flags.
4. **`mismatch_equipment_invoice_4.pdf`**: Equipment invoice with $80.00 discrepancy. Triggers **V01 (Total Mismatch)**.
5. **`missing_tax_seminar_invoice_5.pdf`**: Conference invoice with omitted tax number. Triggers **V02 (Missing Tax Number)**.
6. **`out_of_term_software_invoice_6.pdf`**: Software invoice dated May 15, 2026. Triggers **V04 (Outside Academic Term)**.

---

## 5. Getting Started

### Prerequisites
- Python 3.10+ (tested on Python 3.14)
- Node.js 18+ and npm

### Environment Configuration
The application reads configuration from `.env`. Ensure your `.env` contains:

```env
AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT=https://<your-resource-name>.cognitiveservices.azure.com/
AZURE_DOCUMENT_INTELLIGENCE_KEY=your_azure_api_key_here
AZURE_API_VERSION=2024-11-30
ACADEMIC_TERM_START=2026-08-01
ACADEMIC_TERM_END=2026-12-31
CONFIDENCE_THRESHOLD=0.85
DATABASE_URL=sqlite:///./fee_auditor.db
BACKEND_PORT=8000
```
*(Reference placeholder template is available in `.env.example`)*

---

### Running the Backend

1. Install Python dependencies:
   ```powershell
   pip install -r backend/requirements.txt
   ```

2. Start the FastAPI server:
   ```powershell
   python -m uvicorn app.main:app --app-dir backend --reload --port 8000
   ```
   Interactive OpenAPI documentation will be available at: `http://localhost:8000/docs`

---

### Running the Frontend

1. Install frontend dependencies:
   ```powershell
   cd frontend
   npm install
   ```

2. Start the Vite development server:
   ```powershell
   npm run dev
   ```
   The dashboard will be available at: `http://localhost:5173`

---

## 6. Running Automated Tests

Run the complete test suite (unit tests, API integration, live Azure extraction, and Milestone 6 test cases):

```powershell
python -m pytest backend/tests -v
```

### Verified Test Results:
```text
backend/tests/test_api.py::test_health_endpoint PASSED                   [  6%]
backend/tests/test_api.py::test_document_lifecycle_and_review PASSED     [ 13%]
backend/tests/test_audit_milestone6.py::test_a1_clean_invoice_extraction PASSED [ 20%]
backend/tests/test_audit_milestone6.py::test_a2_total_mismatch_and_missing_tax_validation PASSED [ 26%]
backend/tests/test_audit_milestone6.py::test_a3_duplicate_upload_and_low_confidence PASSED [ 33%]
backend/tests/test_azure_integration.py::test_azure_connection_status PASSED [ 40%]
backend/tests/test_azure_integration.py::test_file_hash_computation PASSED [ 46%]
backend/tests/test_azure_integration.py::test_live_invoice_extraction PASSED [ 53%]
backend/tests/test_validator.py::test_v01_total_mismatch_clean PASSED    [ 60%]
backend/tests/test_validator.py::test_v01_total_mismatch_flagged PASSED  [ 66%]
backend/tests/test_validator.py::test_v02_missing_tax_number PASSED      [ 73%]
backend/tests/test_validator.py::test_v03_duplicate_invoice PASSED       [ 80%]
backend/tests/test_validator.py::test_v04_outside_academic_term PASSED   [ 86%]
backend/tests/test_validator.py::test_v05_low_confidence PASSED          [ 93%]
backend/tests/test_validator.py::test_apply_all_rules_clean_and_flagged PASSED [100%]

============================= 15 passed in 55.67s =============================
```

---

## 7. API Endpoints

- `GET /api/health` — System health check and Azure AI configuration status.
- `POST /api/audit/upload` — Batch multipart document ingestion (`files: List[UploadFile]`, `preferred_model: Optional[str]`).
- `POST /api/audit/load-samples` — 1-click batch ingestion of the 6 synthetic test invoices.
- `GET /api/audit/documents` — Query all audited documents with status filtering (`clean`, `flagged`, `reviewed`).
- `GET /api/audit/documents/{id}` — Retrieve detailed document extraction, field confidences, line items, and audit flags.
- `PATCH /api/audit/documents/{id}/review` — Update manual review status (`approved`, `rejected`, `pending`) and auditor notes.
- `GET /api/audit/summary` — Aggregate metrics for dashboard cards.
- `GET /api/audit/export/csv` — Stream full audit results as a Pandas-generated CSV file.
- `DELETE /api/audit/reset` — Reset database for clean testing cycles.
