from datetime import date
from decimal import Decimal
import pytest

from app.schemas.common import FieldStatus
from app.schemas.document import (
    DocumentExtraction,
    ExtractedField,
    ExtractedLineItem,
)
from app.services.validator import (
    validate_v01_total_mismatch,
    validate_v02_missing_tax_number,
    validate_v03_duplicate_invoice,
    validate_v04_outside_academic_term,
    validate_v05_low_confidence,
    apply_all_validation_rules,
)


def make_sample_doc(
    total="100.00",
    subtotal="90.00",
    tax="10.00",
    items=None,
    tax_id="TAX-12345",
    invoice_id="INV-001",
    invoice_date="2026-09-15",
    confidence=0.95,
    file_hash="hash_abc123",
) -> DocumentExtraction:
    if items is None:
        items = [
            ExtractedLineItem(item_index=0, description="Item A", amount="50.00", confidence=confidence),
            ExtractedLineItem(item_index=1, description="Item B", amount="40.00", confidence=confidence),
        ]
    return DocumentExtraction(
        file_name="test.pdf",
        file_hash=file_hash,
        model_used="prebuilt-invoice",
        document_type="invoice",
        vendor_name=ExtractedField(value="ACME Labs", confidence=confidence),
        invoice_id=ExtractedField(value=invoice_id, confidence=confidence),
        invoice_date=ExtractedField(value=invoice_date, confidence=confidence),
        vendor_tax_id=ExtractedField(
            value=tax_id,
            confidence=confidence if tax_id else None,
            status=FieldStatus.EXTRACTED if tax_id and tax_id.strip() else FieldStatus.MISSING,
        ),
        subtotal=ExtractedField(value=str(subtotal) if subtotal is not None else None, confidence=confidence),
        tax=ExtractedField(value=str(tax) if tax is not None else "0.00", confidence=confidence),
        total=ExtractedField(value=str(total) if total is not None else None, confidence=confidence),
        line_items=items,
    )


def test_v01_total_mismatch_clean():
    # 50 + 40 + 10 tax = 100
    doc = make_sample_doc(total="100.00", tax="10.00")
    flag = validate_v01_total_mismatch(doc)
    assert flag is None


def test_v01_total_mismatch_flagged():
    # 50 + 40 + 10 tax = 100, but total is 125.00
    doc = make_sample_doc(total="125.00", tax="10.00")
    flag = validate_v01_total_mismatch(doc)
    assert flag is not None
    assert flag.rule_id == "V01"
    assert flag.severity == "CRITICAL"
    assert "Discrepancy: $25.00" in flag.reason


def test_v02_missing_tax_number():
    doc_clean = make_sample_doc(tax_id="TAX-9988")
    assert validate_v02_missing_tax_number(doc_clean) is None

    doc_missing = make_sample_doc(tax_id=None)
    flag = validate_v02_missing_tax_number(doc_missing)
    assert flag is not None
    assert flag.rule_id == "V02"
    assert flag.severity == "MEDIUM"

    doc_empty = make_sample_doc(tax_id="   ")
    assert validate_v02_missing_tax_number(doc_empty) is not None


def test_v03_duplicate_invoice():
    known_hashes = {"hash_existing_123"}
    known_invs = {("acme labs", "INVEXISTING"): "prior_file.pdf"}

    # Exact file duplicate
    doc_exact = make_sample_doc(file_hash="hash_existing_123")
    flag_exact = validate_v03_duplicate_invoice(doc_exact, known_hashes, known_invs)
    assert flag_exact is not None
    assert doc_exact.is_exact_duplicate is True
    assert flag_exact.rule_id == "V03"

    # Duplicate invoice ID
    doc_dup_id = make_sample_doc(file_hash="hash_unique_456", invoice_id="INV-EXISTING")
    flag_dup = validate_v03_duplicate_invoice(doc_dup_id, known_hashes, known_invs)
    assert flag_dup is not None
    assert "prior_file.pdf" in flag_dup.reason

    # Clean unique
    doc_clean = make_sample_doc(file_hash="hash_new_789", invoice_id="INV-BRAND-NEW")
    assert validate_v03_duplicate_invoice(doc_clean, known_hashes, known_invs) is None


def test_v04_outside_academic_term():
    term_start = date(2026, 8, 1)
    term_end = date(2026, 12, 31)

    # Valid date within term
    doc_valid = make_sample_doc(invoice_date="2026-10-15")
    assert validate_v04_outside_academic_term(doc_valid, term_start, term_end) is None

    # Before term
    doc_early = make_sample_doc(invoice_date="2026-06-15")
    flag_early = validate_v04_outside_academic_term(doc_early, term_start, term_end)
    assert flag_early is not None
    assert flag_early.rule_id == "V04"

    # After term
    doc_late = make_sample_doc(invoice_date="2027-01-10")
    flag_late = validate_v04_outside_academic_term(doc_late, term_start, term_end)
    assert flag_late is not None

    # Missing date
    doc_missing = make_sample_doc(invoice_date=None)
    flag_missing = validate_v04_outside_academic_term(doc_missing, term_start, term_end)
    assert flag_missing is not None


def test_v05_low_confidence():
    # All confidences 0.95 >= 0.85
    doc_high = make_sample_doc(confidence=0.95)
    assert len(validate_v05_low_confidence(doc_high, threshold=0.85)) == 0

    # Low confidence on total (0.75 < 0.85)
    doc_low = make_sample_doc(confidence=0.95)
    doc_low.total.confidence = 0.75
    flags = validate_v05_low_confidence(doc_low, threshold=0.85)
    assert len(flags) == 1
    assert flags[0].rule_id == "V05"
    assert flags[0].field_name == "total"
    assert flags[0].severity == "WARNING"


def test_apply_all_rules_clean_and_flagged():
    doc_clean = make_sample_doc()
    res_clean = apply_all_validation_rules(doc_clean)
    assert res_clean.audit_status == "clean"
    assert len(res_clean.validation_flags) == 0

    # Mismatch + Missing Tax ID
    doc_flagged = make_sample_doc(total="999.00", tax_id=None)
    res_flagged = apply_all_validation_rules(doc_flagged)
    assert res_flagged.audit_status == "flagged"
    assert len(res_flagged.validation_flags) >= 2
    rule_ids = [f.rule_id for f in res_flagged.validation_flags]
    assert "V01" in rule_ids
    assert "V02" in rule_ids

