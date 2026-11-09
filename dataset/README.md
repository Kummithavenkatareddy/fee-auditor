# P05 — Fee Receipt & Invoice Auditor Synthetic QA Dataset

## 1. Dataset Purpose
This test dataset provides a controlled, ground-truthed suite of synthetic financial documents to evaluate the end-to-end performance of the **P05 — Fee Receipt & Invoice Auditor** system. 

The application architecture utilizes:
1. **Azure AI Document Intelligence**: Prebuilt `Invoice` (`prebuilt-invoice`) and `Receipt` (`prebuilt-receipt`) extraction models.
2. **Python Validation Engine**: A downstream business rules engine executing arithmetic recalculations, compliance checks, and term temporal boundaries.

## 2. Document Descriptions
The dataset contains exactly six documents formatted for Indian business and higher education environments, denominated in Indian Rupees (₹):

* **INV-001.pdf**: Standard commercial office supplies invoice issued by *Aster Office Supplies Pvt. Ltd.* Demonstrates a flawless corporate transaction with full CGST/SGST tax attribution.
* **INV-002.pdf**: IT peripherals and networking hardware invoice issued by *BluePeak IT Solutions*. Demonstrates clean interstate IGST billing to an educational institution.
* **REC-003.pdf**: College semester fee receipt issued by *Greenfield Technical Institute*. Features clear visual separation between the receipt identifier (`REC-2026-003`) and the student enrollment code (`STU-TEST-003`).
* **INV-004.pdf**: Audio-visual classroom hardware invoice issued by *Crestline Equipment Traders*. Visually indistinguishable from a standard document, but contains a deliberate computational error on the printed total.
* **INV-005.pdf**: Educational laboratory equipment invoice from *Meridian Educational Technologies*. Omits the mandatory vendor GSTIN/tax identifier while maintaining valid line-item arithmetic.
* **REC-006.pdf**: Academic term fee receipt issued by *Greenfield Technical Institute* bearing a payment realization date outside the authorized semester term.

## 3. Academic Term Configuration
The academic term is parameterized as follows:
* **Academic Term Label**: Fall Semester 2026
* **Term Start Date**: `01 August 2026` (`2026-08-01`)
* **Term End Date**: `31 December 2026` (`2026-12-31`)
* **Inclusive Boundary Rule**: T_start <= D_document <= T_end

## 4. Seeded Defect Profiles & Validation Rules

| Document ID | Seeded Defect | Injected Value | Ground Truth Value | Triggered Audit Flag | Expected Verdict |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **INV-001** | None | Grand Total: ₹9,794 | Grand Total: ₹9,794 | None | **CLEAN** |
| **INV-002** | None | Grand Total: ₹8,850 | Grand Total: ₹8,850 | None | **CLEAN** |
| **REC-003** | None | Grand Total: ₹29,000 | Grand Total: ₹29,000 | None | **CLEAN** |
| **INV-004** | Tampered Total | Grand Total: **₹55,920** | Sum: **₹51,920** | `FLAG V01 — TOTAL MISMATCH` | **FLAGGED** |
| **INV-005** | Missing Tax ID | Field Omitted | Mandatory Field | `FLAG V02 — MISSING TAX NUMBER` | **FLAGGED** |
| **REC-006** | Out-of-Term Date| Date: **15 Jan 2027** | Max: **31 Dec 2026** | `FLAG V04 — DATE OUTSIDE ACADEMIC TERM`| **FLAGGED** |

## 5. Privacy & Synthetic Data Compliance
* **Zero Real Entities**: All business and institutional entities (*Aster Office Supplies*, *BluePeak IT Solutions*, *Greenfield Technical Institute*, *Crestline Equipment Traders*, *Meridian Educational Technologies*) are fictional.
* **Synthetic Identifiers**: Tax identifiers use the reserved test schema `FAKE-GST-XXXXXX`, preventing collisions with active Ministry of Finance GSTIN records.
* **OCR Optimizations**: Standard TrueType fonts (`DejaVuSans` and `DejaVuSans-Bold`) with explicit vector glyph mappings for the Rupee symbol (`₹`) guarantee high OCR confidence and prevent bounding box artifacts.
