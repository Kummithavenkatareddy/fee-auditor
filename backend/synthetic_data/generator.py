import os
import json
from pathlib import Path
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib import colors

SAMPLES_DIR = Path(__file__).parent / "samples"
GROUND_TRUTH_PATH = Path(__file__).parent / "ground_truth.json"


def draw_invoice(
    filepath: Path,
    doc_title: str,
    vendor_name: str,
    tax_id: str | None,
    invoice_id: str,
    invoice_date: str,
    bill_to: str,
    items: list[dict],
    subtotal: float,
    tax: float,
    total: float,
    notes: str = "",
):
    """Draw a professional, high-clarity PDF invoice with ReportLab."""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(filepath), pagesize=letter)
    width, height = letter

    # Primary header banner
    c.setFillColor(colors.HexColor("#1e293b"))
    c.rect(0, height - 80, width, 80, fill=True, stroke=False)

    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 20)
    c.drawString(40, height - 48, doc_title.upper())

    c.setFont("Helvetica", 10)
    c.drawRightString(width - 40, height - 48, f"Document #: {invoice_id}")

    # Vendor Block
    c.setFillColor(colors.HexColor("#0f172a"))
    c.setFont("Helvetica-Bold", 14)
    c.drawString(40, height - 120, vendor_name)

    c.setFont("Helvetica", 10)
    c.setFillColor(colors.HexColor("#475569"))
    curr_y = height - 138

    if tax_id:
        c.drawString(40, curr_y, f"Tax ID: {tax_id}")
        curr_y -= 16

    c.drawString(40, curr_y, "Academic & Enterprise Services")
    curr_y -= 16
    c.drawString(40, curr_y, "Email: billing@academic-vendor.org")

    # Invoice Metadata Block (Right Side)
    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(colors.HexColor("#1e293b"))
    c.drawRightString(width - 150, height - 120, "Invoice Date:")
    c.drawRightString(width - 150, height - 136, "Academic Term:")
    c.drawRightString(width - 150, height - 152, "Payment Terms:")

    c.setFont("Helvetica", 10)
    c.setFillColor(colors.HexColor("#0f172a"))
    c.drawString(width - 140, height - 120, invoice_date)
    c.drawString(width - 140, height - 136, "Fall 2026")
    c.drawString(width - 140, height - 152, "Due on Receipt")

    # Bill To Box
    c.setStrokeColor(colors.HexColor("#e2e8f0"))
    c.setFillColor(colors.HexColor("#f8fafc"))
    c.roundRect(40, height - 230, width - 80, 50, 4, fill=True, stroke=True)

    c.setFont("Helvetica-Bold", 9)
    c.setFillColor(colors.HexColor("#64748b"))
    c.drawString(55, height - 195, "BILL TO:")
    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(colors.HexColor("#0f172a"))
    c.drawString(55, height - 212, bill_to)

    # Table Header
    table_top = height - 265
    c.setFillColor(colors.HexColor("#334155"))
    c.rect(40, table_top, width - 80, 24, fill=True, stroke=False)

    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(55, table_top + 7, "ITEM DESCRIPTION")
    c.drawRightString(350, table_top + 7, "QTY")
    c.drawRightString(440, table_top + 7, "UNIT PRICE")
    c.drawRightString(width - 55, table_top + 7, "AMOUNT")

    # Table Rows
    row_y = table_top - 24
    c.setFont("Helvetica", 9)
    c.setFillColor(colors.HexColor("#1e293b"))

    for i, item in enumerate(items):
        bg = colors.HexColor("#f8fafc") if i % 2 == 1 else colors.white
        c.setFillColor(bg)
        c.rect(40, row_y - 4, width - 80, 20, fill=True, stroke=False)

        c.setFillColor(colors.HexColor("#1e293b"))
        c.drawString(55, row_y + 3, str(item["description"]))
        c.drawRightString(350, row_y + 3, str(item["quantity"]))
        c.drawRightString(440, row_y + 3, f"${item['unit_price']:,.2f}")
        c.drawRightString(width - 55, row_y + 3, f"${item['amount']:,.2f}")
        row_y -= 22

    # Divider line
    c.setStrokeColor(colors.HexColor("#cbd5e1"))
    c.line(40, row_y + 10, width - 40, row_y + 10)

    # Totals Section
    totals_y = row_y - 10
    c.setFont("Helvetica", 10)
    c.setFillColor(colors.HexColor("#475569"))

    c.drawRightString(width - 150, totals_y, "Subtotal:")
    c.drawRightString(width - 55, totals_y, f"${subtotal:,.2f}")

    totals_y -= 18
    c.drawRightString(width - 150, totals_y, "Tax:")
    c.drawRightString(width - 55, totals_y, f"${tax:,.2f}")

    totals_y -= 22
    c.setFillColor(colors.HexColor("#0f172a"))
    c.setFont("Helvetica-Bold", 12)
    c.drawRightString(width - 150, totals_y, "Total Amount Due:")
    c.drawRightString(width - 55, totals_y, f"${total:,.2f}")

    # Optional footer notes
    if notes:
        c.setFont("Helvetica-Oblique", 8)
        c.setFillColor(colors.HexColor("#94a3b8"))
        c.drawString(40, 50, notes)

    c.showPage()
    c.save()


def generate_all_synthetic_documents():
    """Generate the 6 fictional synthetic documents and ground truth JSON."""
    SAMPLES_DIR.mkdir(parents=True, exist_ok=True)

    documents = [
        # 1. Clean Document 1
        {
            "filename": "clean_tuition_invoice_1.pdf",
            "title": "Tuition Fee Invoice",
            "vendor_name": "Cambridge Institute of Technology",
            "tax_id": "99-1010001",
            "invoice_id": "CIT-2026-901",
            "invoice_date": "2026-09-10",
            "bill_to": "Student Accounts Division — Ref #STU-99014",
            "items": [
                {"description": "Tuition Fee - Advanced Computer Science", "quantity": 1, "unit_price": 1200.0, "amount": 1200.0},
                {"description": "Laboratory Access & Simulation Fee", "quantity": 1, "unit_price": 300.0, "amount": 300.0},
            ],
            "subtotal": 1500.0,
            "tax": 0.0,
            "total": 1500.0,
            "expected_audit_status": "clean",
            "expected_flags": [],
            "test_category": "Clean Invoice (Tuition)",
        },
        # 2. Clean Document 2
        {
            "filename": "clean_campus_store_receipt_2.pdf",
            "title": "University Bookstore Receipt",
            "vendor_name": "Acropolis University Bookstore",
            "tax_id": "88-2020002",
            "invoice_id": "AUB-REC-4412",
            "invoice_date": "2026-10-05",
            "bill_to": "Student Academic Services — Fall Grant",
            "items": [
                {"description": "Distributed Systems Core Principles Book", "quantity": 1, "unit_price": 85.0, "amount": 85.0},
                {"description": "Scientific Graphing Calculator TI-84", "quantity": 1, "unit_price": 115.0, "amount": 115.0},
            ],
            "subtotal": 200.0,
            "tax": 16.0,
            "total": 216.0,
            "expected_audit_status": "clean",
            "expected_flags": [],
            "test_category": "Clean Receipt (Books & Equipment)",
        },
        # 3. Clean Document 3
        {
            "filename": "clean_library_membership_invoice_3.pdf",
            "title": "Library Research Consortium Invoice",
            "vendor_name": "National Academic Library Consortium",
            "tax_id": "77-3030003",
            "invoice_id": "NALC-2026-782",
            "invoice_date": "2026-11-12",
            "bill_to": "Dean of Research & Departmental Subscriptions",
            "items": [
                {"description": "Annual Digital Repository Database Subscription", "quantity": 1, "unit_price": 450.0, "amount": 450.0},
            ],
            "subtotal": 450.0,
            "tax": 22.50,
            "total": 472.50,
            "expected_audit_status": "clean",
            "expected_flags": [],
            "test_category": "Clean Invoice (Subscription)",
        },
        # 4. Total Mismatch (V01)
        {
            "filename": "mismatch_equipment_invoice_4.pdf",
            "title": "Laboratory Equipment Invoice",
            "vendor_name": "Apex Lab Scientific Equipment Inc",
            "tax_id": "66-4040004",
            "invoice_id": "APEX-2026-551",
            "invoice_date": "2026-09-22",
            "bill_to": "Biomedical Engineering Laboratory",
            "items": [
                {"description": "Digital Precision Scale 0.001g", "quantity": 1, "unit_price": 250.0, "amount": 250.0},
                {"description": "Oscilloscope Probe Kit 100MHz", "quantity": 2, "unit_price": 75.0, "amount": 150.0},
            ],
            "subtotal": 400.0,
            "tax": 40.0,
            # Calculated sum = 440.0, but stated total = 520.0
            "total": 520.0,
            "expected_audit_status": "flagged",
            "expected_flags": ["V01"],
            "test_category": "Total Mismatch ($80.00 artificial discrepancy)",
        },
        # 5. Missing Tax Number (V02)
        {
            "filename": "missing_tax_seminar_invoice_5.pdf",
            "title": "Professional Conference Invoice",
            "vendor_name": "Global Tech Summit Foundation",
            "tax_id": None,  # Intentionally missing!
            "invoice_id": "GTSF-2026-302",
            "invoice_date": "2026-10-18",
            "bill_to": "Graduate Research Travel Fund",
            "items": [
                {"description": "Student Conference Registration Pass", "quantity": 2, "unit_price": 100.0, "amount": 200.0},
            ],
            "subtotal": 200.0,
            "tax": 0.0,
            "total": 200.0,
            "expected_audit_status": "flagged",
            "expected_flags": ["V02"],
            "test_category": "Missing Tax Identifier",
        },
        # 6. Outside Academic Term (V04)
        {
            "filename": "out_of_term_software_invoice_6.pdf",
            "title": "Software Licensing Invoice",
            "vendor_name": "CloudSim Simulation Systems",
            "tax_id": "44-6060006",
            "invoice_id": "CSS-2026-119",
            # Intentionally May 15, 2026 (Academic Term is 2026-08-01 to 2026-12-31)
            "invoice_date": "2026-05-15",
            "bill_to": "Computer Science Department",
            "items": [
                {"description": "Cloud Simulation License 1-Month", "quantity": 1, "unit_price": 95.0, "amount": 95.0},
            ],
            "subtotal": 95.0,
            "tax": 5.0,
            "total": 100.0,
            "expected_audit_status": "flagged",
            "expected_flags": ["V04"],
            "test_category": "Outside Academic Term (Pre-term: May 2026)",
        },
    ]

    ground_truth = {}

    for doc in documents:
        out_path = SAMPLES_DIR / doc["filename"]
        draw_invoice(
            filepath=out_path,
            doc_title=doc["title"],
            vendor_name=doc["vendor_name"],
            tax_id=doc["tax_id"],
            invoice_id=doc["invoice_id"],
            invoice_date=doc["invoice_date"],
            bill_to=doc["bill_to"],
            items=doc["items"],
            subtotal=doc["subtotal"],
            tax=doc["tax"],
            total=doc["total"],
            notes=f"Synthetic test document for Fee Auditor. Category: {doc['test_category']}",
        )
        print(f"Generated: {out_path.name}")

        ground_truth[doc["filename"]] = {
            "vendor_name": doc["vendor_name"],
            "tax_id": doc["tax_id"],
            "invoice_id": doc["invoice_id"],
            "invoice_date": doc["invoice_date"],
            "subtotal": doc["subtotal"],
            "tax": doc["tax"],
            "total": doc["total"],
            "line_items_count": len(doc["items"]),
            "expected_audit_status": doc["expected_audit_status"],
            "expected_flags": doc["expected_flags"],
            "test_category": doc["test_category"],
        }

    with open(GROUND_TRUTH_PATH, "w", encoding="utf-8") as f:
        json.dump(ground_truth, f, indent=2)

    print(f"Ground truth saved to: {GROUND_TRUTH_PATH}")


if __name__ == "__main__":
    generate_all_synthetic_documents()

