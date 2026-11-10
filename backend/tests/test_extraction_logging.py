import json
import logging
from decimal import Decimal
import pytest

from app.schemas.common import (
    FieldStatus,
    ExtractedField,
    ExtractedLineItem,
    ValidationFlag,
    FinancialReconciliation,
    TaxBreakdown,
)
from app.schemas.invoice import InvoiceData
from app.schemas.receipt import ReceiptData
from app.schemas.document import DocumentExtraction
from app.utils.extraction_report_formatter import (
    format_extraction_report,
    format_invoice_summary,
    format_receipt_summary,
    format_validation_summary,
    format_currency,
    format_confidence,
)


def _build_sample_invoice() -> DocumentExtraction:
    """Helper to build a complete canonical invoice extraction."""
    return DocumentExtraction(
        id="doc-inv-001-uuid",
        file_name="INV-001.pdf",
        original_filename="INV-001.pdf",
        file_hash="a1b2c3d4e5f67890123456789abcdef0123456789abcdef0123456789abcdef0",
        sha256_hash="a1b2c3d4e5f67890123456789abcdef0123456789abcdef0123456789abcdef0",
        storage_key="documents/user1/2026/09/INV-001.pdf",
        model_used="prebuilt-invoice",
        document_type="invoice",
        extraction_status="succeeded",
        processing_status="completed",
        invoice_data=InvoiceData(
            vendor_name=ExtractedField(value="BLUEPEAK IT SOLUTIONS PVT LTD", confidence=0.885, status=FieldStatus.EXTRACTED, confidence_source="azure"),
            customer_name=ExtractedField(value="NATIONAL INSTITUTE OF TECHNOLOGY", confidence=0.912, status=FieldStatus.EXTRACTED, confidence_source="azure"),
            invoice_id=ExtractedField(value="INV-2026-001", confidence=0.950, status=FieldStatus.EXTRACTED, confidence_source="azure"),
            invoice_date=ExtractedField(value="2026-09-15", confidence=0.920, status=FieldStatus.EXTRACTED, confidence_source="azure"),
            vendor_tax_id=ExtractedField(value="29ABCDE1234F1Z5", confidence=0.910, status=FieldStatus.EXTRACTED, confidence_source="azure"),
        ),
        vendor_name=ExtractedField(value="BLUEPEAK IT SOLUTIONS PVT LTD", confidence=0.885, status=FieldStatus.EXTRACTED, confidence_source="azure"),
        invoice_id=ExtractedField(value="INV-2026-001", confidence=0.950, status=FieldStatus.EXTRACTED, confidence_source="azure"),
        invoice_date=ExtractedField(value="2026-09-15", confidence=0.920, status=FieldStatus.EXTRACTED, confidence_source="azure"),
        vendor_tax_id=ExtractedField(value="29ABCDE1234F1Z5", confidence=0.910, status=FieldStatus.EXTRACTED, confidence_source="azure"),
        subtotal=ExtractedField(value="8300.00", confidence=0.940, status=FieldStatus.EXTRACTED, confidence_source="azure"),
        cgst=ExtractedField(value="747.00", confidence=0.910, status=FieldStatus.EXTRACTED, confidence_source="azure"),
        sgst=ExtractedField(value="747.00", confidence=0.910, status=FieldStatus.EXTRACTED, confidence_source="azure"),
        tax=ExtractedField(value="1494.00", confidence=0.930, status=FieldStatus.EXTRACTED, confidence_source="azure"),
        total=ExtractedField(value="9794.00", confidence=0.960, status=FieldStatus.EXTRACTED, confidence_source="azure"),
        line_items=[
            ExtractedLineItem(item_index=1, description="Campus Network Switch 24-Port", quantity="1.00", unit_price="5500.00", amount="5500.00", confidence=0.920),
            ExtractedLineItem(item_index=2, description="Cat6 Ethernet Patch Cable 50m", quantity="2.00", unit_price="1400.00", amount="2800.00", confidence=0.895),
        ],
        reconciliation=FinancialReconciliation(
            line_items_sum="8300.00",
            extracted_subtotal="8300.00",
            cgst="747.00",
            sgst="747.00",
            total_tax="1494.00",
            expected_grand_total="9794.00",
            extracted_grand_total="9794.00",
            variance="0.00",
            calculation_type="tax_exclusive",
            is_reconciled=True,
            status="RECONCILED",
            explanation="Line items sum ₹8,300.00 matches subtotal. Tax-exclusive formula (₹8,300.00 + ₹1,494.00) matches grand total ₹9,794.00.",
        ),
        validation_flags=[],
        audit_status="clean",
        manual_review_status="pending",
        raw_azure_json='{"status": "succeeded", "canary_token": "RAW_AZURE_SECRET_TOKEN_12345"}',
    )


def _build_sample_receipt() -> DocumentExtraction:
    """Helper to build a complete canonical receipt extraction."""
    return DocumentExtraction(
        id="doc-rec-003-uuid",
        file_name="REC-003.pdf",
        original_filename="REC-003.pdf",
        file_hash="b2c3d4e5f67890123456789abcdef0123456789abcdef0123456789abcdef01",
        sha256_hash="b2c3d4e5f67890123456789abcdef0123456789abcdef0123456789abcdef01",
        storage_key="documents/user1/2026/09/REC-003.pdf",
        model_used="prebuilt-receipt",
        document_type="receipt",
        extraction_status="succeeded",
        processing_status="completed",
        receipt_data=ReceiptData(
            merchant_name=ExtractedField(value="APEX INSTITUTE OF TECHNOLOGY", confidence=0.955, status=FieldStatus.EXTRACTED, confidence_source="azure"),
            transaction_date=ExtractedField(value="2026-09-20", confidence=0.940, status=FieldStatus.EXTRACTED, confidence_source="azure"),
            subtotal=ExtractedField(value="1500.00", confidence=0.950, status=FieldStatus.EXTRACTED, confidence_source="azure"),
            tax=ExtractedField(value=None, confidence=None, status=FieldStatus.NOT_APPLICABLE, confidence_source="azure"),
            total=ExtractedField(value="1500.00", confidence=0.970, status=FieldStatus.EXTRACTED, confidence_source="azure"),
            items=[
                ExtractedLineItem(item_index=1, description="Semester Examination Fee", quantity="1.00", unit_price="1500.00", amount="1500.00", confidence=0.950)
            ],
        ),
        vendor_name=ExtractedField(value="APEX INSTITUTE OF TECHNOLOGY", confidence=0.955, status=FieldStatus.EXTRACTED, confidence_source="azure"),
        invoice_id=ExtractedField(value="REC-2026-003", confidence=None, status=FieldStatus.EXTRACTED, confidence_source="ocr_fallback"),
        invoice_date=ExtractedField(value="2026-09-20", confidence=0.940, status=FieldStatus.EXTRACTED, confidence_source="azure"),
        vendor_tax_id=ExtractedField(value=None, confidence=None, status=FieldStatus.NOT_APPLICABLE, confidence_source="azure"),
        subtotal=ExtractedField(value="1500.00", confidence=0.950, status=FieldStatus.EXTRACTED, confidence_source="azure"),
        tax=ExtractedField(value=None, confidence=None, status=FieldStatus.NOT_APPLICABLE, confidence_source="azure"),
        total=ExtractedField(value="1500.00", confidence=0.970, status=FieldStatus.EXTRACTED, confidence_source="azure"),
        line_items=[
            ExtractedLineItem(item_index=1, description="Semester Examination Fee", quantity="1.00", unit_price="1500.00", amount="1500.00", confidence=0.950)
        ],
        reconciliation=FinancialReconciliation(
            line_items_sum="1500.00",
            extracted_subtotal="1500.00",
            total_tax=None,
            expected_grand_total="1500.00",
            extracted_grand_total="1500.00",
            variance="0.00",
            calculation_type="tax_inclusive",
            is_reconciled=True,
            status="RECONCILED",
            explanation="Line items sum ₹1,500.00 matches total amount ₹1,500.00 (Exempt statutory fee).",
        ),
        validation_flags=[],
        audit_status="clean",
        manual_review_status="pending",
        raw_azure_json='{"status": "succeeded", "docType": "receipt"}',
    )


# =============================================================================
# SCENARIO 1: Invoice Formatted Output
# =============================================================================
def test_01_invoice_formatted_output():
    doc = _build_sample_invoice()
    report = format_extraction_report(doc, use_colors=False)

    # Master Header
    assert "AZURE AI DOCUMENT INTELLIGENCE" in report
    assert "Document File:        INV-001.pdf" in report
    assert "Invoice (Model: prebuilt-invoice)" in report
    assert "Processing Status:    COMPLETED" in report
    assert "Document ID:          doc-inv-001-uuid" in report

    # Section 1: Extracted Document Information
    assert "1. EXTRACTED DOCUMENT INFORMATION (Invoice Prebuilt Model)" in report
    assert "Vendor / Payee Name        BLUEPEAK IT SOLUTIONS PVT LTD" in report
    assert "Customer / Buyer Name      NATIONAL INSTITUTE OF TECHNO" in report
    assert "Invoice Number             INV-2026-001" in report
    assert "Invoice Date               2026-09-15" in report
    assert "Vendor Tax ID (GSTIN)      29ABCDE1234F1Z5" in report

    # Section 2: Financial Summary
    assert "2. FINANCIAL SUMMARY" in report
    assert "Subtotal (Taxable Base)              ₹8,300.00" in report
    assert "Central GST (CGST)                   ₹747.00" in report
    assert "State GST (SGST)                     ₹747.00" in report
    assert "Total Tax / GST                      ₹1,494.00" in report
    assert "Grand Total                          ₹9,794.00" in report

    # Section 3: Line Items
    assert "3. LINE ITEMS (Extracted Items Count: 2)" in report
    assert "Campus Network Switch 24-Port" in report
    assert "Cat6 Ethernet Patch Cable 50m" in report
    assert "Line Items Computed Sum:" in report
    assert "₹8,300.00" in report

    # Section 4: Financial Reconciliation
    assert "4. FINANCIAL RECONCILIATION ENGINE (Rule V01)" in report
    assert "Method:               Tax-Exclusive (Subtotal + GST/Taxes = Grand Total)" in report
    assert "Reconciliation Status: PASS / RECONCILED" in report
    assert "Net Variance:            ₹0.00 (Within institutional ₹0.02 tolerance)" in report

    # Section 5 & 6: Validation & Audit Summary
    assert "5. VALIDATION FINDINGS" in report
    assert "[PASS] Zero exceptions detected" in report
    assert "6. FINAL AUDIT SUMMARY & COMPLIANCE VERDICT" in report
    assert "Overall Audit Status:     CLEAN / VALIDATED" in report
    assert "Validation Flags Count:   0" in report


# =============================================================================
# SCENARIO 2: Receipt Formatted Output
# =============================================================================
def test_02_receipt_formatted_output():
    doc = _build_sample_receipt()
    report = format_extraction_report(doc, use_colors=False)

    # Master Header
    assert "Document File:        REC-003.pdf" in report
    assert "Receipt (Model: prebuilt-receipt)" in report

    # Section 1: Receipt Specific Fields
    assert "1. EXTRACTED DOCUMENT INFORMATION (Receipt Prebuilt Model)" in report
    assert "Merchant / Payee Name      APEX INSTITUTE OF TECHNOLOGY    95.5%" in report
    assert "Receipt / Reference ID     REC-2026-003                    --" in report
    assert "Transaction Date           2026-09-20                      94.0%" in report
    assert "Vendor Tax ID (GSTIN)      [EXEMPT / NOT APPLICABLE]       --" in report

    # Section 2: Financial Summary for Exempt Receipts
    assert "2. FINANCIAL SUMMARY" in report
    assert "Subtotal (Taxable Base)              ₹1,500.00" in report
    assert "Total Tax / GST                      [EXEMPT]" in report
    assert "Grand Total                          ₹1,500.00" in report

    # Section 3: Line Items
    assert "Semester Examination Fee" in report
    assert "₹1,500.00" in report

    # Section 4: Reconciliation
    assert "4. FINANCIAL RECONCILIATION ENGINE" in report
    assert "PASS / RECONCILED" in report

    # Section 6: Audit Summary
    assert "CLEAN / VALIDATED" in report
    assert "Validation Flags Count:   0" in report


# =============================================================================
# SCENARIO 3: Missing Fields Handled Truthfully
# =============================================================================
def test_03_missing_fields():
    doc = _build_sample_invoice()
    # Simulate missing tax ID on invoice (Rule V02 violation)
    doc.vendor_tax_id = ExtractedField(value=None, confidence=None, status=FieldStatus.MISSING)
    doc.invoice_data.vendor_tax_id = doc.vendor_tax_id
    doc.validation_flags.append(
        ValidationFlag(
            rule_id="V02",
            rule_name="Missing Vendor Tax ID",
            severity="CRITICAL",
            field_name="vendor_tax_id",
            reason="Commercial tax invoice requires valid 15-character GSTIN.",
            expected_value="15-character GSTIN",
            actual_value="Missing",
        )
    )
    doc.audit_status = "flagged"
    doc.highest_severity = "CRITICAL"

    report = format_extraction_report(doc, use_colors=False)

    # Section 1 should state [MISSING]
    assert "Vendor Tax ID (GSTIN)      [MISSING]                       --" in report
    assert "MISSING" in report

    # Section 5 should detail the V02 finding
    assert "[CRITICAL] #1 Rule V02: Missing Vendor Tax ID" in report
    assert "Target Field:   vendor_tax_id" in report

    # Section 6 should count missing fields
    assert "Missing Fields:           1 (vendor_tax_id)" in report
    assert "FLAGGED (CRITICAL)" in report


# =============================================================================
# SCENARIO 4: Null Confidence Handled Cleanly Without Crashing
# =============================================================================
def test_04_null_confidence():
    doc = _build_sample_invoice()
    doc.vendor_name.confidence = None
    if doc.invoice_data:
        doc.invoice_data.vendor_name.confidence = None
    doc.subtotal.confidence = None
    doc.total.confidence = None
    doc.line_items[0].confidence = None

    report = format_extraction_report(doc, use_colors=False)

    assert "BLUEPEAK IT SOLUTIONS PVT LTD" in report
    assert "--" in report
    assert "Subtotal (Taxable Base)              ₹8,300.00" in report
    assert "Campus Network Switch 24-Port" in report


# =============================================================================
# SCENARIO 5: OCR Fallback Provenance Traceability
# =============================================================================
def test_05_ocr_fallback_provenance():
    doc = _build_sample_invoice()
    doc.invoice_id = ExtractedField(
        value="INV-FALLBACK-99",
        confidence=None,
        status=FieldStatus.EXTRACTED,
        confidence_source="ocr_fallback",
    )
    doc.invoice_data.invoice_id = doc.invoice_id

    report = format_extraction_report(doc, use_colors=False)
    assert "Invoice Number             INV-FALLBACK-99                 --         EXTRACTED        OCR Fallback" in report


# =============================================================================
# SCENARIO 6: Multiple Tax Components (CGST + SGST + IGST + Cess)
# =============================================================================
def test_06_multiple_tax_components():
    doc = _build_sample_invoice()
    doc.igst = ExtractedField(value="500.00", confidence=0.89, status=FieldStatus.EXTRACTED)
    doc.cess = ExtractedField(value="100.00", confidence=0.91, status=FieldStatus.EXTRACTED)
    doc.reconciliation.igst = "500.00"
    doc.reconciliation.cess = "100.00"

    report = format_extraction_report(doc, use_colors=False)

    # Section 2 should display itemized components
    assert "Central GST (CGST)                   ₹747.00" in report
    assert "State GST (SGST)                     ₹747.00" in report
    assert "Integrated GST (IGST)                ₹500.00" in report
    assert "Cess                                 ₹100.00" in report

    # Section 4 should detail them in the breakdown
    assert "CGST: ₹747.00, SGST: ₹747.00, IGST: ₹500.00, Cess: ₹100.00" in report


# =============================================================================
# SCENARIO 7: Low-Confidence Warnings (<85%)
# =============================================================================
def test_07_low_confidence_warnings():
    doc = _build_sample_invoice()
    doc.vendor_name.confidence = 0.659
    doc.vendor_name.status = FieldStatus.LOW_CONFIDENCE
    if doc.invoice_data:
        doc.invoice_data.vendor_name.confidence = 0.659
        doc.invoice_data.vendor_name.status = FieldStatus.LOW_CONFIDENCE
    doc.validation_flags.append(
        ValidationFlag(
            rule_id="V05",
            rule_name="Low Extraction Confidence",
            severity="WARNING",
            field_name="vendor_name",
            reason="Vendor / Payee Name confidence 65.9% is below institutional 85.0% threshold.",
            expected_value=">= 85.0%",
            actual_value="65.9%",
        )
    )
    doc.audit_status = "flagged"
    doc.highest_severity = "WARNING"

    report = format_extraction_report(doc, use_colors=False)

    # Section 1
    assert "65.9%" in report
    assert "LOW_CONFIDENCE" in report

    # Section 5
    assert "[WARNING] #1 Rule V05: Low Extraction Confidence" in report

    # Section 6
    assert "Low-Confidence Fields:    1 (vendor_name (65.9%))" in report
    assert "Overall Audit Status:     FLAGGED (WARNING)" in report


# =============================================================================
# SCENARIO 8: Multiple Validation Findings (V01, V02, V04, V05)
# =============================================================================
def test_08_multiple_validation_findings():
    doc = _build_sample_invoice()
    doc.validation_flags = [
        ValidationFlag(
            rule_id="V01",
            rule_name="Total Mismatch",
            severity="CRITICAL",
            field_name="total",
            reason="Sum of line items (₹8,300.00) plus GST does not match grand total ₹9,794.00.",
            expected_value="9794.00",
            actual_value="8300.00",
        ),
        ValidationFlag(
            rule_id="V02",
            rule_name="Missing Vendor Tax ID",
            severity="HIGH",
            field_name="vendor_tax_id",
            reason="Commercial tax invoice requires valid GSTIN.",
            expected_value="15-character GSTIN",
            actual_value="Missing",
        ),
        ValidationFlag(
            rule_id="V04",
            rule_name="Outside Academic Term",
            severity="HIGH",
            field_name="invoice_date",
            reason="Invoice date 2026-05-10 is outside academic term (2026-08-01 to 2026-12-31).",
            expected_value="2026-08-01 to 2026-12-31",
            actual_value="2026-05-10",
        ),
    ]
    doc.audit_status = "flagged"
    doc.highest_severity = "CRITICAL"

    report = format_extraction_report(doc, use_colors=False)

    assert "Rules V01-V05 Evaluated: 3 Finding(s)" in report
    assert "[CRITICAL] #1 Rule V01: Total Mismatch" in report
    assert "[HIGH] #2 Rule V02: Missing Vendor Tax ID" in report
    assert "[HIGH] #3 Rule V04: Outside Academic Term" in report
    assert "Validation Flags Count:   3" in report
    assert "Overall Audit Status:     FLAGGED (CRITICAL)" in report


# =============================================================================
# SCENARIO 9: Failed Extraction Handled Gracefully
# =============================================================================
def test_09_failed_extraction():
    failed_doc = DocumentExtraction(
        file_name="CORRUPT_PAYLOAD.pdf",
        file_hash="deadbeef12345678",
        model_used="prebuilt-invoice",
        document_type="invoice",
        extraction_status="failed",
        processing_status="failed",
    )

    report = format_extraction_report(failed_doc, use_colors=False)

    assert "Processing Status:    FAILED (Extraction: failed)" in report
    assert "EXTRACTION FAILURE: Azure Document Intelligence was unable to extract structured data." in report
    # Should not crash attempting to format line items or financial summaries
    assert "Document File:        CORRUPT_PAYLOAD.pdf" in report


# =============================================================================
# SCENARIO 10: UTF-8 & INR Formatting
# =============================================================================
def test_10_utf8_and_inr_formatting():
    # Test formatting with default ₹ symbol
    assert format_currency("11800.00", symbol="₹") == "₹11,800.00"
    assert format_currency(Decimal("8300.50"), symbol="₹") == "₹8,300.50"
    assert format_currency("-500.00", symbol="₹") == "-₹500.00"
    assert format_currency(0, symbol="₹") == "₹0.00"
    assert format_currency(None, symbol="₹") == "--"

    # Test formatting with custom INR symbol
    assert format_currency("9794.00", symbol="INR ") == "INR 9,794.00"
    assert format_currency("9794.00", symbol="INR") == "INR 9,794.00"

    # Test confidence formatting to exactly one decimal place
    assert format_confidence(0.885) == "88.5%"
    assert format_confidence(0.96) == "96.0%"
    assert format_confidence(0.659) == "65.9%"
    assert format_confidence(None) == "--"


# =============================================================================
# SCENARIO 11: Plain-Text Output Without ANSI Escape Sequences
# =============================================================================
def test_11_plain_text_without_ansi_codes():
    doc = _build_sample_invoice()

    # Plain-text report (default)
    plain_report = format_extraction_report(doc, use_colors=False)
    assert "\033[" not in plain_report
    assert "\033[0m" not in plain_report

    # Color report
    color_report = format_extraction_report(doc, use_colors=True)
    assert "\033[" in color_report
    assert "\033[0m" in color_report


# =============================================================================
# SCENARIO 12: No Raw JSON Leakage into Normal INFO Logs
# =============================================================================
def test_12_no_raw_json_leakage_into_normal_info_logs(caplog):
    doc = _build_sample_invoice()
    assert "RAW_AZURE_SECRET_TOKEN_12345" in doc.raw_azure_json

    # Report string MUST NOT contain the raw JSON dump
    report = format_extraction_report(doc, use_colors=False)
    assert "RAW_AZURE_SECRET_TOKEN_12345" not in report
    assert "canary_token" not in report

    # Test logging behavior
    logger = logging.getLogger("test_orchestrator")
    with caplog.at_level(logging.INFO, logger="test_orchestrator"):
        logger.info("\n%s", report)
        # Raw JSON only logged at DEBUG
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug("Raw: %s", doc.raw_azure_json)

    # In INFO log record: report is present, raw JSON is absent
    assert "AZURE AI DOCUMENT INTELLIGENCE" in caplog.text
    assert "RAW_AZURE_SECRET_TOKEN_12345" not in caplog.text
