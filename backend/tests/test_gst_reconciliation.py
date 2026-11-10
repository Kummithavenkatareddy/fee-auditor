"""
P06 — GST-Aware Financial Reconciliation Engine (Rule V01) Comprehensive Test Suite
Validates the 16 mandatory test scenarios specified in P06 requirements.
"""

from decimal import Decimal
from pathlib import Path
import pytest

from app.schemas.common import FieldStatus, ExtractedField, ExtractedLineItem
from app.schemas.document import DocumentExtraction
from app.services.validator import validate_v01_total_mismatch, apply_all_validation_rules
from app.services.extractor import extract_document


def create_test_invoice(
    total="1000.00",
    subtotal="1000.00",
    tax="0.00",
    cgst=None,
    sgst=None,
    igst=None,
    cess=None,
    other_tax=None,
    discounts=None,
    additional_charges=None,
    rounding_adjustment=None,
    items=None,
    tax_status=FieldStatus.EXTRACTED,
    total_status=FieldStatus.EXTRACTED,
    doc_type="invoice",
) -> DocumentExtraction:
    """Helper to construct DocumentExtraction with granular tax and adjustment components."""
    if items is None and subtotal is not None:
        # Default single matching line item
        items = [
            ExtractedLineItem(
                item_index=0,
                description="General Line Item",
                quantity="1.00",
                unit_price=str(subtotal),
                amount=str(subtotal),
                confidence=0.95,
            )
        ]

    return DocumentExtraction(
        file_name="test_invoice.pdf",
        file_hash="mock_hash_123456",
        model_used="prebuilt-invoice" if doc_type == "invoice" else "prebuilt-receipt",
        document_type=doc_type,
        vendor_name=ExtractedField(value="National Enterprise Ltd.", confidence=0.95),
        invoice_id=ExtractedField(value="INV-2026-TEST", confidence=0.95),
        invoice_date=ExtractedField(value="2026-09-15", confidence=0.95),
        vendor_tax_id=ExtractedField(value="FAKE-GST-99999", confidence=0.95),
        subtotal=ExtractedField(value=str(subtotal) if subtotal is not None else None, confidence=0.95),
        cgst=ExtractedField(value=str(cgst) if cgst is not None else None, confidence=0.95),
        sgst=ExtractedField(value=str(sgst) if sgst is not None else None, confidence=0.95),
        igst=ExtractedField(value=str(igst) if igst is not None else None, confidence=0.95),
        cess=ExtractedField(value=str(cess) if cess is not None else None, confidence=0.95),
        other_tax=ExtractedField(value=str(other_tax) if other_tax is not None else None, confidence=0.95),
        discounts=ExtractedField(value=str(discounts) if discounts is not None else None, confidence=0.95),
        additional_charges=ExtractedField(value=str(additional_charges) if additional_charges is not None else None, confidence=0.95),
        rounding_adjustment=ExtractedField(value=str(rounding_adjustment) if rounding_adjustment is not None else None, confidence=0.95),
        tax=ExtractedField(
            value=str(tax) if tax is not None else None,
            confidence=0.95 if tax is not None else None,
            status=tax_status if tax is None else FieldStatus.EXTRACTED,
        ),
        total=ExtractedField(
            value=str(total) if total is not None else None,
            confidence=0.95 if total is not None else None,
            status=total_status if total is None else FieldStatus.EXTRACTED,
        ),
        line_items=items or [],
    )


# ---------------------------------------------------------------------------
# SCENARIO 1: GST invoice with CGST + SGST — passes.
# ---------------------------------------------------------------------------
def test_scenario_01_gst_invoice_cgst_sgst_clean():
    """1. GST invoice with CGST + SGST — passes without V01 flag."""
    # INV-001 canonical values: Subtotal 8300 + CGST 747 + SGST 747 = Total 9794
    doc = create_test_invoice(
        subtotal="8300.00",
        cgst="747.00",
        sgst="747.00",
        tax="1494.00",
        total="9794.00",
        items=[
            ExtractedLineItem(item_index=0, description="Paper", amount="2500.00", confidence=0.95),
            ExtractedLineItem(item_index=1, description="Toner", amount="4800.00", confidence=0.95),
            ExtractedLineItem(item_index=2, description="Files", amount="1000.00", confidence=0.95),
        ],
    )
    flag = validate_v01_total_mismatch(doc)
    assert flag is None, f"Expected clean reconciliation, got flag: {flag}"
    assert doc.reconciliation is not None
    assert doc.reconciliation.is_reconciled is True
    assert doc.reconciliation.status == "RECONCILED"
    assert doc.reconciliation.calculation_type == "tax_exclusive"
    assert doc.reconciliation.expected_grand_total == "9794.00"
    assert doc.reconciliation.variance == "0.00"
    assert doc.reconciliation.cgst == "747.00"
    assert doc.reconciliation.sgst == "747.00"
    assert doc.reconciliation.total_tax == "1494.00"


# ---------------------------------------------------------------------------
# SCENARIO 2: IGST invoice — passes.
# ---------------------------------------------------------------------------
def test_scenario_02_igst_invoice_clean():
    """2. IGST interstate invoice — passes without V01 flag."""
    # Subtotal 10,000 + IGST 1,800 (18%) = Total 11,800
    doc = create_test_invoice(
        subtotal="10000.00",
        igst="1800.00",
        tax="1800.00",
        total="11800.00",
        items=[
            ExtractedLineItem(item_index=0, description="Server Hosting", amount="10000.00", confidence=0.95),
        ],
    )
    flag = validate_v01_total_mismatch(doc)
    assert flag is None
    assert doc.reconciliation.is_reconciled is True
    assert doc.reconciliation.status == "RECONCILED"
    assert doc.reconciliation.calculation_type == "tax_exclusive"
    assert doc.reconciliation.igst == "1800.00"
    assert doc.reconciliation.expected_grand_total == "11800.00"
    assert doc.reconciliation.variance == "0.00"


# ---------------------------------------------------------------------------
# SCENARIO 3: Invoice with CGST + SGST + cess — passes.
# ---------------------------------------------------------------------------
def test_scenario_03_gst_cgst_sgst_cess_clean():
    """3. Invoice with CGST + SGST + cess — passes."""
    # Subtotal 10,000 + CGST 700 + SGST 700 + Cess 100 = Total 11,500
    doc = create_test_invoice(
        subtotal="10000.00",
        cgst="700.00",
        sgst="700.00",
        cess="100.00",
        tax="1500.00",
        total="11500.00",
    )
    flag = validate_v01_total_mismatch(doc)
    assert flag is None
    assert doc.reconciliation.is_reconciled is True
    assert doc.reconciliation.status == "RECONCILED"
    assert doc.reconciliation.cess == "100.00"
    assert doc.reconciliation.effective_tax == "1500.00"
    assert doc.reconciliation.expected_grand_total == "11500.00"


# ---------------------------------------------------------------------------
# SCENARIO 4: Genuine tax-exclusive grand-total mismatch — triggers V01.
# ---------------------------------------------------------------------------
def test_scenario_04_genuine_tax_exclusive_grand_total_mismatch():
    """4. Genuine tax-exclusive grand-total mismatch — triggers V01."""
    # Subtotal 10,000 + CGST 900 + SGST 900 = Expected 11,800. Stated: 15,000 (Discrepancy 3,200)
    doc = create_test_invoice(
        subtotal="10000.00",
        cgst="900.00",
        sgst="900.00",
        tax="1800.00",
        total="15000.00",
    )
    flag = validate_v01_total_mismatch(doc)
    assert flag is not None
    assert flag.rule_id == "V01"
    assert flag.severity == "CRITICAL"
    assert "3200.00" in flag.reason
    assert doc.reconciliation.is_reconciled is False
    assert doc.reconciliation.status == "MISMATCH"
    assert doc.reconciliation.expected_grand_total == "11800.00"
    assert doc.reconciliation.extracted_grand_total == "15000.00"
    assert doc.reconciliation.variance == "3200.00"


# ---------------------------------------------------------------------------
# SCENARIO 5: Tax-inclusive invoice — passes without adding tax twice.
# ---------------------------------------------------------------------------
def test_scenario_05_tax_inclusive_invoice_clean():
    """5. Tax-inclusive invoice — passes without adding tax twice."""
    # Stated line items & subtotal 11,800 incorporate tax; tax breakdown states 1,800 info
    # Grand total is 11,800. Adding 1,800 again would yield 13,600 (incorrect).
    doc = create_test_invoice(
        subtotal="11800.00",
        cgst="900.00",
        sgst="900.00",
        tax="1800.00",
        total="11800.00",
        items=[
            ExtractedLineItem(item_index=0, description="Equipment (Tax Incl)", amount="11800.00", confidence=0.95),
        ],
    )
    flag = validate_v01_total_mismatch(doc)
    assert flag is None
    assert doc.reconciliation.is_reconciled is True
    assert doc.reconciliation.status == "RECONCILED"
    assert doc.reconciliation.calculation_type == "tax_inclusive"
    assert doc.reconciliation.expected_grand_total == "11800.00"
    assert doc.reconciliation.variance == "0.00"


# ---------------------------------------------------------------------------
# SCENARIO 6: Aggregate TotalTax plus CGST/SGST — no double-counting.
# ---------------------------------------------------------------------------
def test_scenario_06_aggregate_totaltax_plus_cgst_sgst_no_double_counting():
    """6. Aggregate TotalTax plus CGST/SGST — no double-counting."""
    # Subtotal 5,000 + CGST 450 + SGST 450 + TotalTax 900 -> Expected total 5,900 (NOT 6,800)
    doc = create_test_invoice(
        subtotal="5000.00",
        cgst="450.00",
        sgst="450.00",
        tax="900.00",
        total="5900.00",
    )
    flag = validate_v01_total_mismatch(doc)
    assert flag is None
    assert doc.reconciliation.is_reconciled is True
    assert doc.reconciliation.effective_tax == "900.00"
    assert doc.reconciliation.expected_grand_total == "5900.00"
    assert doc.reconciliation.variance == "0.00"


# ---------------------------------------------------------------------------
# SCENARIO 7: Invoice with discount — correct reconciliation.
# ---------------------------------------------------------------------------
def test_scenario_07_invoice_with_discount():
    """7. Invoice with discount — correct reconciliation."""
    # Subtotal 10,000 - Discount 1,000 + Tax 1,620 = Total 10,620
    doc = create_test_invoice(
        subtotal="10000.00",
        discounts="1000.00",
        tax="1620.00",
        total="10620.00",
    )
    flag = validate_v01_total_mismatch(doc)
    assert flag is None
    assert doc.reconciliation.is_reconciled is True
    assert doc.reconciliation.discounts == "1000.00"
    assert doc.reconciliation.expected_grand_total == "10620.00"
    assert doc.reconciliation.variance == "0.00"


# ---------------------------------------------------------------------------
# SCENARIO 8: Invoice with shipping charges — correct reconciliation.
# ---------------------------------------------------------------------------
def test_scenario_08_invoice_with_shipping_charges():
    """8. Invoice with shipping charges — correct reconciliation."""
    # Subtotal 5,000 + Shipping 250 + Tax 900 = Total 6,150
    doc = create_test_invoice(
        subtotal="5000.00",
        additional_charges="250.00",
        tax="900.00",
        total="6150.00",
    )
    flag = validate_v01_total_mismatch(doc)
    assert flag is None
    assert doc.reconciliation.is_reconciled is True
    assert doc.reconciliation.additional_charges == "250.00"
    assert doc.reconciliation.expected_grand_total == "6150.00"
    assert doc.reconciliation.variance == "0.00"


# ---------------------------------------------------------------------------
# SCENARIO 9: Invoice with rounding adjustment — correct reconciliation.
# ---------------------------------------------------------------------------
def test_scenario_09_invoice_with_rounding_adjustment():
    """9. Invoice with rounding adjustment — correct reconciliation."""
    # Subtotal 1000.35 + Tax 180.06 - Rounding 0.41 = Total 1180.00
    doc = create_test_invoice(
        subtotal="1000.35",
        tax="180.06",
        rounding_adjustment="-0.41",
        total="1180.00",
    )
    flag = validate_v01_total_mismatch(doc)
    assert flag is None
    assert doc.reconciliation.is_reconciled is True
    assert doc.reconciliation.rounding_adjustment == "-0.41"
    assert doc.reconciliation.expected_grand_total == "1180.00"
    assert doc.reconciliation.variance == "0.00"


# ---------------------------------------------------------------------------
# SCENARIO 10: Line-item sum differing from subtotal — triggers V01.
# ---------------------------------------------------------------------------
def test_scenario_10_line_item_sum_differing_from_subtotal():
    """10. Line-item sum differing from subtotal — triggers V01."""
    # Line items: 4000 + 3000 = 7000. Subtotal declared: 8000. Discrepancy: 1000
    doc = create_test_invoice(
        subtotal="8000.00",
        tax="1440.00",
        total="9440.00",
        items=[
            ExtractedLineItem(item_index=0, description="Item 1", amount="4000.00", confidence=0.95),
            ExtractedLineItem(item_index=1, description="Item 2", amount="3000.00", confidence=0.95),
        ],
    )
    flag = validate_v01_total_mismatch(doc)
    assert flag is not None
    assert flag.rule_id == "V01"
    assert flag.rule_name == "Line Items Mismatch"
    assert flag.severity == "HIGH"
    assert "1000.00" in flag.reason
    assert doc.reconciliation.is_reconciled is False
    assert doc.reconciliation.status == "MANUAL_REVIEW_REQUIRED"
    assert doc.reconciliation.variance == "1000.00"


# ---------------------------------------------------------------------------
# SCENARIO 11: Missing tax information — manual review.
# ---------------------------------------------------------------------------
def test_scenario_11_missing_tax_information_manual_review():
    """11. Missing tax information — manual review when reconciliation cannot be established."""
    # Subtotal 10,000, Total 11,800, but tax is Missing
    doc = create_test_invoice(
        subtotal="10000.00",
        tax=None,
        tax_status=FieldStatus.MISSING,
        total="11800.00",
    )
    flag = validate_v01_total_mismatch(doc)
    assert flag is not None
    assert flag.rule_id == "V01"
    assert flag.rule_name == "Missing Tax Information"
    assert flag.severity == "HIGH"
    assert doc.reconciliation.status == "MANUAL_REVIEW_REQUIRED"
    assert doc.reconciliation.calculation_type == "ambiguous"


# ---------------------------------------------------------------------------
# SCENARIO 12: Partial line-item extraction — manual review.
# ---------------------------------------------------------------------------
def test_scenario_12_partial_line_item_extraction_manual_review():
    """12. Partial line-item extraction — manual review."""
    # Document has 2 items, but item 2 lacks an amount
    doc = create_test_invoice(
        subtotal="1500.00",
        tax="270.00",
        total="1770.00",
        items=[
            ExtractedLineItem(item_index=0, description="Item A", amount="1000.00", confidence=0.95),
            ExtractedLineItem(item_index=1, description="Item B", amount=None, confidence=None),
        ],
    )
    flag = validate_v01_total_mismatch(doc)
    assert flag is not None
    assert flag.rule_id == "V01"
    assert flag.rule_name == "Partial Line-Item Extraction"
    assert flag.severity == "HIGH"
    assert doc.reconciliation.status == "MANUAL_REVIEW_REQUIRED"


# ---------------------------------------------------------------------------
# SCENARIO 13: Missing grand total — manual review.
# ---------------------------------------------------------------------------
def test_scenario_13_missing_grand_total_manual_review():
    """13. Missing grand total — manual review."""
    doc = create_test_invoice(
        subtotal="5000.00",
        tax="900.00",
        total=None,
        total_status=FieldStatus.MISSING,
    )
    flag = validate_v01_total_mismatch(doc)
    assert flag is not None
    assert flag.rule_id == "V01"
    assert flag.rule_name == "Grand Total Missing / Invalid"
    assert flag.severity == "HIGH"
    assert doc.reconciliation.status == "MANUAL_REVIEW_REQUIRED"


# ---------------------------------------------------------------------------
# SCENARIO 14: Currency tolerance boundary — correct behavior.
# ---------------------------------------------------------------------------
def test_scenario_14_currency_tolerance_boundary():
    """14. Currency tolerance boundary (tolerance = ₹0.02)."""
    # 100.00 + 18.00 = 118.00
    # Difference of 0.02 must pass
    doc_pass = create_test_invoice(subtotal="100.00", tax="18.00", total="118.02")
    assert validate_v01_total_mismatch(doc_pass) is None
    assert doc_pass.reconciliation.is_reconciled is True

    # Difference of 0.03 must fail
    doc_fail = create_test_invoice(subtotal="100.00", tax="18.00", total="118.03")
    flag_fail = validate_v01_total_mismatch(doc_fail)
    assert flag_fail is not None
    assert flag_fail.rule_id == "V01"
    assert flag_fail.severity == "CRITICAL"
    assert doc_fail.reconciliation.is_reconciled is False


# ---------------------------------------------------------------------------
# SCENARIO 15: Existing seeded mismatch invoice INV-004.pdf — remains flagged.
# ---------------------------------------------------------------------------
def test_scenario_15_existing_seeded_mismatch_invoice_inv004():
    """15. Existing seeded mismatch invoice INV-004.pdf — remains flagged with ₹4,000 discrepancy."""
    # Subtotal 44,000 + Tax 7,920 = Expected 51,920. Stated: 55,920 (Diff: 4,000)
    samples_dir = Path(__file__).resolve().parent.parent / "synthetic_data" / "samples"
    inv4_path = samples_dir / "INV-004.pdf"
    if inv4_path.exists():
        extracted = extract_document(inv4_path.read_bytes(), "INV-004.pdf")
        validated = apply_all_validation_rules(extracted)
        v01_flags = [f for f in validated.validation_flags if f.rule_id == "V01"]
        assert len(v01_flags) == 1
        assert v01_flags[0].severity == "CRITICAL"
        assert "4000.00" in v01_flags[0].reason
        assert validated.reconciliation.status == "MISMATCH"
        assert validated.reconciliation.variance == "4000.00"
    else:
        # Mock equivalent if file not in test env
        doc = create_test_invoice(
            subtotal="44000.00",
            tax="7920.00",
            total="55920.00",
            items=[ExtractedLineItem(item_index=0, amount="44000.00", confidence=0.95)],
        )
        flag = validate_v01_total_mismatch(doc)
        assert flag is not None
        assert flag.severity == "CRITICAL"
        assert "4000.00" in flag.reason


# ---------------------------------------------------------------------------
# SCENARIO 16: Receipt documents — existing behavior remains intact.
# ---------------------------------------------------------------------------
def test_scenario_16_receipt_documents_clean_intact():
    """16. Receipt documents — existing clean behavior remains intact."""
    # REC-003: Fee receipt Subtotal 29,000, Tax 0, Total 29,000
    doc = create_test_invoice(
        subtotal="29000.00",
        tax="0.00",
        total="29000.00",
        doc_type="receipt",
        items=[
            ExtractedLineItem(item_index=0, description="Semester Tuition Fee", amount="29000.00", confidence=0.95),
        ],
    )
    flag = validate_v01_total_mismatch(doc)
    assert flag is None
    assert doc.reconciliation.is_reconciled is True
    assert doc.reconciliation.status == "RECONCILED"
    assert doc.reconciliation.variance == "0.00"

