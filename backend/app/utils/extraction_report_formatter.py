"""
Human-Readable Document Extraction and Audit Report Formatter.

Produces structured, institutional terminal extraction summaries for invoices and receipts
processed via Azure AI Document Intelligence and deterministic Python validation (V01-V05).
Compatible with Windows terminals, standard UTF-8, and plain-text project reports.
"""

from decimal import Decimal, InvalidOperation
from typing import Optional, List, Any, Tuple
import re

from app.schemas.common import FieldStatus, ExtractedField, ExtractedLineItem, FinancialReconciliation
from app.schemas.document import DocumentExtraction, ValidationFlag


# ANSI Terminal Colors (applied only when use_colors=True)
_CLR_RESET = "\033[0m"
_CLR_BOLD = "\033[1m"
_CLR_GREEN = "\033[32m"
_CLR_YELLOW = "\033[33m"
_CLR_RED = "\033[31m"
_CLR_CYAN = "\033[36m"
_CLR_BLUE = "\033[34m"
_CLR_DIM = "\033[2m"


def _c(text: str, code: str, use_colors: bool) -> str:
    """Conditionally wrap text in ANSI escape sequence."""
    if not use_colors or not code:
        return text
    return f"{code}{text}{_CLR_RESET}"


def format_currency(val: Any, symbol: str = "₹") -> str:
    """Format any numeric or currency string to two decimal places with thousands separators."""
    if val is None:
        return "--"
    try:
        if isinstance(val, Decimal):
            dec_val = val
        else:
            clean = re.sub(r"[^\d.-]", "", str(val).strip())
            if not clean or clean == "-":
                return "--"
            dec_val = Decimal(clean)
        
        # Determine prefix and formatting
        is_negative = dec_val < 0
        abs_dec = abs(dec_val)
        formatted_num = f"{abs_dec:,.2f}"
        
        # Include a space after multi-character currency codes like 'INR '
        prefix = f"{symbol} " if len(symbol) > 1 and not symbol.endswith(" ") else symbol
        
        if is_negative:
            return f"-{prefix}{formatted_num}"
        return f"{prefix}{formatted_num}"
    except (InvalidOperation, ValueError, TypeError):
        return str(val)


def format_confidence(conf: Optional[float]) -> str:
    """Format confidence float to percentage with one decimal place."""
    if conf is None:
        return "--"
    try:
        val = float(conf)
        # If score is > 1.0 (e.g. 88.5 passed as percentage), normalize
        if val > 1.0:
            return f"{val:.1f}%"
        return f"{val * 100:.1f}%"
    except (ValueError, TypeError):
        return "--"


def _format_source(source: Optional[str]) -> str:
    """Format confidence provenance source."""
    if not source:
        return "Azure Prebuilt"
    src_lower = source.lower()
    if "ocr" in src_lower or "fallback" in src_lower:
        return "OCR Fallback"
    if "azure" in src_lower:
        return "Azure Prebuilt"
    return source.title()


def _format_status_label(status: Any, use_colors: bool = False) -> str:
    """Format field status with optional color styling."""
    raw_status = getattr(status, "value", str(status or "extracted")).upper()
    if raw_status == "EXTRACTED":
        return _c("EXTRACTED", _CLR_GREEN, use_colors)
    elif raw_status == "LOW_CONFIDENCE":
        return _c("LOW_CONFIDENCE", _CLR_YELLOW, use_colors)
    elif raw_status == "MISSING":
        return _c("MISSING", _CLR_RED, use_colors)
    elif raw_status == "NOT_APPLICABLE":
        return _c("NOT_APPLICABLE", _CLR_DIM, use_colors)
    return raw_status


def _format_field_row(
    label: str,
    field: Optional[ExtractedField],
    use_colors: bool = False,
    is_exempt: bool = False,
    override_val: Optional[str] = None,
) -> str:
    """Format a single field row for Section 1."""
    if is_exempt:
        val_str = "[EXEMPT / NOT APPLICABLE]"
        conf_str = "--"
        status_str = _format_status_label(FieldStatus.NOT_APPLICABLE, use_colors)
        source_str = "N/A"
    elif field is None:
        val_str = "[NOT AVAILABLE]"
        conf_str = "--"
        status_str = _format_status_label(FieldStatus.NOT_APPLICABLE, use_colors)
        source_str = "N/A"
    elif field.status == FieldStatus.MISSING or (field.value is None and not override_val):
        val_str = "[MISSING]"
        conf_str = "--"
        status_str = _format_status_label(FieldStatus.MISSING, use_colors)
        source_str = _format_source(field.confidence_source)
    else:
        raw_val = override_val if override_val is not None else str(field.value or "")
        val_str = (raw_val[:28] + "...") if len(raw_val) > 31 else raw_val
        conf_str = format_confidence(field.confidence)
        status_str = _format_status_label(field.status, use_colors)
        source_str = _format_source(field.confidence_source)

    # Column widths: Label(26), Value(31), Conf(10), Status(16), Source(14)
    # Using plain widths for padding, without ANSI artifacts interfering with column math
    plain_status = getattr(field, "status", FieldStatus.EXTRACTED).value.upper() if field else "NOT_APPLICABLE"
    if is_exempt:
        plain_status = "NOT_APPLICABLE"
    status_pad = " " * max(0, 16 - len(plain_status))

    return f"{label:<26} {val_str:<31} {conf_str:<10} {status_str}{status_pad} {source_str}"


def format_invoice_summary(
    doc: DocumentExtraction,
    use_colors: bool = False,
    currency_symbol: str = "₹",
) -> str:
    """Format Section 1 for invoice documents."""
    lines: List[str] = []
    lines.append(_c("----------------------------------------------------------------------------------------------------", _CLR_DIM, use_colors))
    lines.append(_c("1. EXTRACTED DOCUMENT INFORMATION (Invoice Prebuilt Model)", _CLR_BOLD, use_colors))
    lines.append(_c("----------------------------------------------------------------------------------------------------", _CLR_DIM, use_colors))
    lines.append(f"{'Field':<26} {'Value':<31} {'Confidence':<10} {'Status':<16} {'Source'}")
    lines.append(_c("----------------------------------------------------------------------------------------------------", _CLR_DIM, use_colors))

    # Vendor Name
    v_field = doc.vendor_name or getattr(doc.invoice_data, "vendor_name", None)
    lines.append(_format_field_row("Vendor / Payee Name", v_field, use_colors=use_colors))

    # Customer Name (Invoice specific)
    c_field = getattr(doc.invoice_data, "customer_name", None)
    if c_field and (c_field.value or c_field.status != FieldStatus.NOT_APPLICABLE):
        lines.append(_format_field_row("Customer / Buyer Name", c_field, use_colors=use_colors))

    # Invoice ID
    inv_id = doc.invoice_id or getattr(doc.invoice_data, "invoice_id", None)
    lines.append(_format_field_row("Invoice Number", inv_id, use_colors=use_colors))

    # Invoice Date
    inv_date = doc.invoice_date or getattr(doc.invoice_data, "invoice_date", None)
    lines.append(_format_field_row("Invoice Date", inv_date, use_colors=use_colors))

    # Vendor Tax ID (GSTIN)
    tax_id = doc.vendor_tax_id or getattr(doc.invoice_data, "vendor_tax_id", None)
    lines.append(_format_field_row("Vendor Tax ID (GSTIN)", tax_id, use_colors=use_colors))

    return "\n".join(lines)


def format_receipt_summary(
    doc: DocumentExtraction,
    use_colors: bool = False,
    currency_symbol: str = "₹",
) -> str:
    """Format Section 1 for receipt documents."""
    lines: List[str] = []
    lines.append(_c("----------------------------------------------------------------------------------------------------", _CLR_DIM, use_colors))
    lines.append(_c("1. EXTRACTED DOCUMENT INFORMATION (Receipt Prebuilt Model)", _CLR_BOLD, use_colors))
    lines.append(_c("----------------------------------------------------------------------------------------------------", _CLR_DIM, use_colors))
    lines.append(f"{'Field':<26} {'Value':<31} {'Confidence':<10} {'Status':<16} {'Source'}")
    lines.append(_c("----------------------------------------------------------------------------------------------------", _CLR_DIM, use_colors))

    # Merchant Name
    m_field = getattr(doc.receipt_data, "merchant_name", None) or doc.vendor_name
    lines.append(_format_field_row("Merchant / Payee Name", m_field, use_colors=use_colors))

    # Receipt / Transaction ID
    rec_id = doc.invoice_id
    lines.append(_format_field_row("Receipt / Reference ID", rec_id, use_colors=use_colors))

    # Transaction Date
    t_date = getattr(doc.receipt_data, "transaction_date", None) or doc.invoice_date
    lines.append(_format_field_row("Transaction Date", t_date, use_colors=use_colors))

    # Vendor Tax ID: Receipts in India are exempt or N/A
    is_exempt = doc.vendor_tax_id.status == FieldStatus.NOT_APPLICABLE or not doc.vendor_tax_id.value
    lines.append(_format_field_row("Vendor Tax ID (GSTIN)", doc.vendor_tax_id, use_colors=use_colors, is_exempt=is_exempt))

    return "\n".join(lines)


def _format_financial_summary_section(
    doc: DocumentExtraction,
    use_colors: bool = False,
    currency_symbol: str = "₹",
) -> str:
    """Format Section 2 — Financial Summary with explicit distinction between zero and unavailable."""
    is_receipt = doc.document_type == "receipt"
    lines: List[str] = []
    lines.append(_c("----------------------------------------------------------------------------------------------------", _CLR_DIM, use_colors))
    lines.append(_c(f"2. FINANCIAL SUMMARY (Currency: INR / {currency_symbol.strip()})", _CLR_BOLD, use_colors))
    lines.append(_c("----------------------------------------------------------------------------------------------------", _CLR_DIM, use_colors))
    lines.append(f"{'Financial Component':<36} {'Extracted Amount':<20} {'Confidence':<12} {'Status'}")
    lines.append(_c("----------------------------------------------------------------------------------------------------", _CLR_DIM, use_colors))

    def _fin_row(label: str, field: Optional[ExtractedField], is_tax_exempt: bool = False) -> str:
        if is_tax_exempt:
            amt_str = "[EXEMPT]"
            conf_str = "--"
            status_str = _format_status_label(FieldStatus.NOT_APPLICABLE, use_colors)
            plain_status = "NOT_APPLICABLE"
        elif field is None or (field.value is None and field.status == FieldStatus.NOT_APPLICABLE):
            amt_str = "[NOT APPLICABLE]"
            conf_str = "--"
            status_str = _format_status_label(FieldStatus.NOT_APPLICABLE, use_colors)
            plain_status = "NOT_APPLICABLE"
        elif field.status == FieldStatus.MISSING or field.value is None:
            amt_str = "[MISSING]"
            conf_str = "--"
            status_str = _format_status_label(FieldStatus.MISSING, use_colors)
            plain_status = "MISSING"
        else:
            amt_str = format_currency(field.value, symbol=currency_symbol)
            conf_str = format_confidence(field.confidence)
            status_str = _format_status_label(field.status, use_colors)
            plain_status = getattr(field, "status", FieldStatus.EXTRACTED).value.upper()

        status_pad = " " * max(0, 16 - len(plain_status))
        return f"{label:<36} {amt_str:<20} {conf_str:<12} {status_str}{status_pad}"

    # 1. Subtotal
    lines.append(_fin_row("Subtotal (Taxable Base)", doc.subtotal))

    # 2. CGST (if invoice or explicitly present)
    if doc.cgst and (doc.cgst.value is not None or doc.cgst.status != FieldStatus.NOT_APPLICABLE):
        lines.append(_fin_row("Central GST (CGST)", doc.cgst))

    # 3. SGST (if invoice or explicitly present)
    if doc.sgst and (doc.sgst.value is not None or doc.sgst.status != FieldStatus.NOT_APPLICABLE):
        lines.append(_fin_row("State GST (SGST)", doc.sgst))

    # 4. IGST (if present)
    if doc.igst and (doc.igst.value is not None or doc.igst.status != FieldStatus.NOT_APPLICABLE):
        lines.append(_fin_row("Integrated GST (IGST)", doc.igst))

    # 5. Cess (if present)
    if doc.cess and (doc.cess.value is not None or doc.cess.status != FieldStatus.NOT_APPLICABLE):
        lines.append(_fin_row("Cess", doc.cess))

    # 6. Other Tax (if present)
    if doc.other_tax and (doc.other_tax.value is not None or doc.other_tax.status != FieldStatus.NOT_APPLICABLE):
        lines.append(_fin_row("Other Tax", doc.other_tax))

    # 7. Total Tax / GST
    is_exempt_tax = is_receipt and (doc.tax.status == FieldStatus.NOT_APPLICABLE or doc.tax.value is None)
    lines.append(_fin_row("Total Tax / GST", doc.tax, is_tax_exempt=is_exempt_tax))

    # 8. Discounts (if present)
    if doc.discounts and (doc.discounts.value is not None or doc.discounts.status != FieldStatus.NOT_APPLICABLE):
        lines.append(_fin_row("Discounts", doc.discounts))

    # 9. Additional Charges (if present)
    if doc.additional_charges and (doc.additional_charges.value is not None or doc.additional_charges.status != FieldStatus.NOT_APPLICABLE):
        lines.append(_fin_row("Additional Charges / Shipping", doc.additional_charges))

    # 10. Rounding (if present)
    if doc.rounding_adjustment and (doc.rounding_adjustment.value is not None or doc.rounding_adjustment.status != FieldStatus.NOT_APPLICABLE):
        lines.append(_fin_row("Rounding Adjustment", doc.rounding_adjustment))

    # 11. Grand Total
    lines.append(_fin_row("Grand Total", doc.total))

    return "\n".join(lines)


def _format_line_items_section(
    items: List[ExtractedLineItem],
    use_colors: bool = False,
    currency_symbol: str = "₹",
) -> str:
    """Format Section 3 — Line Items table."""
    lines: List[str] = []
    lines.append(_c("----------------------------------------------------------------------------------------------------", _CLR_DIM, use_colors))
    lines.append(_c(f"3. LINE ITEMS (Extracted Items Count: {len(items)})", _CLR_BOLD, use_colors))
    lines.append(_c("----------------------------------------------------------------------------------------------------", _CLR_DIM, use_colors))

    if not items:
        lines.append("  No line items detected in document payload.")
        return "\n".join(lines)

    lines.append(f"{'#':<3} {'Description':<38} {'Qty':<8} {'Unit Price':<16} {'Amount':<16} {'Confidence'}")
    lines.append(_c("----------------------------------------------------------------------------------------------------", _CLR_DIM, use_colors))

    total_line_sum = Decimal("0.00")
    for idx, item in enumerate(items, start=1):
        desc = (item.description or f"Item #{idx}")
        desc_str = (desc[:35] + "...") if len(desc) > 38 else desc
        qty_str = item.quantity or "1.00"
        unit_str = format_currency(item.unit_price, symbol=currency_symbol) if item.unit_price else "--"
        amt_str = format_currency(item.amount, symbol=currency_symbol) if item.amount else "--"
        conf_str = format_confidence(item.confidence)

        if item.amount:
            try:
                clean_amt = re.sub(r"[^\d.-]", "", str(item.amount))
                total_line_sum += Decimal(clean_amt)
            except Exception:
                pass

        lines.append(f"{idx:<3} {desc_str:<38} {qty_str:<8} {unit_str:<16} {amt_str:<16} {conf_str}")

    lines.append(_c("----------------------------------------------------------------------------------------------------", _CLR_DIM, use_colors))
    lines.append(f"{'':<3} {'Line Items Computed Sum:':<38} {'':<8} {'':<16} {format_currency(total_line_sum, symbol=currency_symbol):<16}")
    return "\n".join(lines)


def _format_reconciliation_section(
    rec: Optional[FinancialReconciliation],
    use_colors: bool = False,
    currency_symbol: str = "₹",
) -> str:
    """Format Section 4 — GST-Aware Financial Reconciliation (Rule V01)."""
    lines: List[str] = []
    lines.append(_c("----------------------------------------------------------------------------------------------------", _CLR_DIM, use_colors))
    lines.append(_c("4. FINANCIAL RECONCILIATION ENGINE (Rule V01)", _CLR_BOLD, use_colors))
    lines.append(_c("----------------------------------------------------------------------------------------------------", _CLR_DIM, use_colors))

    if not rec:
        lines.append("  Reconciliation analysis not available.")
        return "\n".join(lines)

    # Method Label
    method_name = {
        "tax_exclusive": "Tax-Exclusive (Subtotal + GST/Taxes = Grand Total)",
        "tax_inclusive": "Tax-Inclusive (Grand Total Contains GST)",
        "ambiguous": "Ambiguous / Incomplete Structure",
    }.get(rec.calculation_type, rec.calculation_type)

    # Status Label
    if rec.is_reconciled:
        status_label = _c("PASS / RECONCILED", _CLR_GREEN, use_colors)
    elif rec.status == "MANUAL_REVIEW_REQUIRED":
        status_label = _c("MANUAL_REVIEW_REQUIRED", _CLR_YELLOW, use_colors)
    else:
        status_label = _c("FAIL / MISMATCH", _CLR_RED, use_colors)

    lines.append(f"  Method:               {method_name}")
    lines.append(f"  Reconciliation Status: {status_label}")
    lines.append("")
    lines.append("  Reconciliation Components:")
    lines.append(f"    - Line Items Sum:          {format_currency(rec.line_items_sum, symbol=currency_symbol)}")
    lines.append(f"    - Extracted Subtotal:      {format_currency(rec.extracted_subtotal, symbol=currency_symbol)}")

    # Tax Components breakdown
    taxes: List[str] = []
    if rec.cgst:
        taxes.append(f"CGST: {format_currency(rec.cgst, symbol=currency_symbol)}")
    if rec.sgst:
        taxes.append(f"SGST: {format_currency(rec.sgst, symbol=currency_symbol)}")
    if rec.igst:
        taxes.append(f"IGST: {format_currency(rec.igst, symbol=currency_symbol)}")
    if rec.cess:
        taxes.append(f"Cess: {format_currency(rec.cess, symbol=currency_symbol)}")
    if rec.other_tax:
        taxes.append(f"Other: {format_currency(rec.other_tax, symbol=currency_symbol)}")

    tax_detail = ", ".join(taxes) if taxes else "None / Zero"
    tot_tax_str = format_currency(rec.total_tax, symbol=currency_symbol)
    lines.append(f"    - Tax Breakdown:           {tax_detail} (Total Tax: {tot_tax_str})")

    if rec.discounts:
        lines.append(f"    - Discounts:              -{format_currency(rec.discounts, symbol=currency_symbol)}")
    if rec.additional_charges:
        lines.append(f"    - Additional Charges:     +{format_currency(rec.additional_charges, symbol=currency_symbol)}")
    if rec.rounding_adjustment:
        lines.append(f"    - Rounding Adjustment:     {format_currency(rec.rounding_adjustment, symbol=currency_symbol)}")

    lines.append(f"    - Expected Grand Total:    {format_currency(rec.expected_grand_total, symbol=currency_symbol)}")
    lines.append(f"    - Extracted Grand Total:   {format_currency(rec.extracted_grand_total, symbol=currency_symbol)}")

    # Variance
    var_str = format_currency(rec.variance, symbol=currency_symbol)
    if rec.is_reconciled:
        var_note = _c(f"{var_str} (Within institutional ₹0.02 tolerance)", _CLR_GREEN, use_colors)
    else:
        var_note = _c(f"{var_str} (DISCREPANCY DETECTED)", _CLR_RED, use_colors)
    lines.append(f"    - Net Variance:            {var_note}")
    lines.append("")
    lines.append(f"  Result Explanation:   {rec.explanation}")

    return "\n".join(lines)


def format_validation_summary(doc: DocumentExtraction, use_colors: bool = False) -> str:
    """Format Section 5 (Validation Findings) and Section 6 (Final Audit Summary)."""
    flags = doc.validation_flags or []
    lines: List[str] = []

    # Section 5: Validation Findings
    lines.append(_c("----------------------------------------------------------------------------------------------------", _CLR_DIM, use_colors))
    lines.append(_c(f"5. VALIDATION FINDINGS (Rules V01-V05 Evaluated: {len(flags)} Finding(s))", _CLR_BOLD, use_colors))
    lines.append(_c("----------------------------------------------------------------------------------------------------", _CLR_DIM, use_colors))

    if not flags:
        lines.append(f"  {_c('[PASS]', _CLR_GREEN, use_colors)} Zero exceptions detected. All deterministic compliance checks passed.")
    else:
        for idx, flag in enumerate(flags, start=1):
            sev_color = _CLR_RED if flag.severity in ("CRITICAL", "HIGH") else _CLR_YELLOW
            sev_tag = _c(f"[{flag.severity}]", sev_color, use_colors)
            lines.append(f"  {sev_tag} #{idx} Rule {flag.rule_id}: {flag.rule_name}")
            if flag.field_name:
                lines.append(f"    Target Field:   {flag.field_name}")
            lines.append(f"    Audit Reason:   {flag.reason}")
            if flag.expected_value or flag.actual_value:
                lines.append(f"    Discrepancy:    Expected: {flag.expected_value or 'N/A'} | Actual: {flag.actual_value or 'N/A'}")
            lines.append("")

    # Section 6: Final Audit Summary
    lines.append(_c("====================================================================================================", _CLR_BOLD, use_colors))
    lines.append(_c("6. FINAL AUDIT SUMMARY & COMPLIANCE VERDICT", _CLR_BOLD, use_colors))
    lines.append(_c("====================================================================================================", _CLR_BOLD, use_colors))

    # Audit status styling
    status_str = doc.audit_status.upper()
    if status_str == "CLEAN":
        status_styled = _c("CLEAN / VALIDATED", _CLR_GREEN, use_colors)
    elif status_str == "REVIEWED":
        status_styled = _c(f"REVIEWED ({doc.manual_review_status.upper() if doc.manual_review_status else 'PENDING'})", _CLR_BLUE, use_colors)
    else:
        status_styled = _c(f"FLAGGED ({doc.highest_severity or 'WARNING'})", _CLR_RED, use_colors)

    lines.append(f"  Overall Audit Status:     {status_styled}")
    lines.append(f"  Highest Severity:         {doc.highest_severity or 'NONE'}")
    lines.append(f"  Validation Flags Count:   {len(flags)}")

    # Low confidence fields calculation
    low_conf_fields: List[str] = []
    missing_fields: List[str] = []

    fields_to_check = [
        ("vendor_name", doc.vendor_name),
        ("invoice_id", doc.invoice_id),
        ("invoice_date", doc.invoice_date),
        ("vendor_tax_id", doc.vendor_tax_id),
        ("subtotal", doc.subtotal),
        ("total", doc.total),
    ]
    for name, f in fields_to_check:
        if not f:
            continue
        if f.status == FieldStatus.LOW_CONFIDENCE or (f.confidence is not None and f.confidence < 0.85):
            low_conf_fields.append(f"{name} ({format_confidence(f.confidence)})")
        if f.status == FieldStatus.MISSING or (f.value is None and f.status != FieldStatus.NOT_APPLICABLE):
            missing_fields.append(name)

    low_conf_summary = f"{len(low_conf_fields)} ({', '.join(low_conf_fields)})" if low_conf_fields else "0 (All extracted fields >= 85%)"
    missing_summary = f"{len(missing_fields)} ({', '.join(missing_fields)})" if missing_fields else "0"

    lines.append(f"  Low-Confidence Fields:    {low_conf_summary}")
    lines.append(f"  Missing Fields:           {missing_summary}")

    # Manual review requirement
    if doc.manual_review_status in ("approved", "rejected"):
        rev_req = _c(f"DECISION RECORDED ({doc.manual_review_status.upper()})", _CLR_GREEN, use_colors)
    elif doc.audit_status == "flagged" or any(f.severity in ("CRITICAL", "HIGH") for f in flags):
        rev_req = _c("YES (Exceptions require accounts auditor intervention)", _CLR_RED, use_colors)
    elif low_conf_fields:
        rev_req = _c("OPTIONAL (Low-confidence OCR warnings present)", _CLR_YELLOW, use_colors)
    else:
        rev_req = _c("NO (Clean audit clearance)", _CLR_GREEN, use_colors)

    lines.append(f"  Manual Review Required:   {rev_req}")
    lines.append(_c("====================================================================================================", _CLR_BOLD, use_colors))

    return "\n".join(lines)


def format_extraction_report(
    doc: DocumentExtraction,
    use_colors: bool = False,
    currency_symbol: str = "₹",
) -> str:
    """Compile the complete 6-section human-readable document extraction report.

    Args:
        doc: The normalized and validated DocumentExtraction object.
        use_colors: Whether to wrap output in ANSI terminal color sequences (False by default for clean copying).
        currency_symbol: Currency symbol for monetary figures (default: '₹').

    Returns:
        Structured string report ready for terminal logging or project report embedding.
    """
    sections: List[str] = []

    # Master Header
    status_header = doc.processing_status.upper() if doc.processing_status else "COMPLETED"
    is_failed = doc.extraction_status == "failed"
    status_styled = _c("FAILED", _CLR_RED, use_colors) if is_failed else _c(status_header, _CLR_GREEN, use_colors)

    sections.append(_c("====================================================================================================", _CLR_BOLD, use_colors))
    sections.append(_c("                     AZURE AI DOCUMENT INTELLIGENCE — EXTRACTION REPORT", _CLR_BOLD, use_colors))
    sections.append(_c("====================================================================================================", _CLR_BOLD, use_colors))
    sections.append(f"  Document File:        {doc.original_filename or doc.file_name}")
    sections.append(f"  Document Type:        {doc.document_type.capitalize()} (Model: {doc.model_used})")
    sections.append(f"  Processing Status:    {status_styled} (Extraction: {doc.extraction_status})")
    sections.append(f"  Document ID:          {doc.id or 'Unassigned'}")
    sections.append(f"  SHA-256 Hash:         {doc.sha256_hash or doc.file_hash}")
    if doc.storage_key:
        sections.append(f"  Persistent Storage:   {doc.storage_key}")

    if is_failed:
        sections.append(_c("====================================================================================================", _CLR_RED, use_colors))
        sections.append(_c("  EXTRACTION FAILURE: Azure Document Intelligence was unable to extract structured data.", _CLR_RED, use_colors))
        sections.append(_c("====================================================================================================", _CLR_RED, use_colors))
        return "\n".join(sections)

    # Section 1: Extracted Document Information
    if doc.document_type == "receipt":
        sections.append(format_receipt_summary(doc, use_colors=use_colors, currency_symbol=currency_symbol))
    else:
        sections.append(format_invoice_summary(doc, use_colors=use_colors, currency_symbol=currency_symbol))

    # Section 2: Financial Summary
    sections.append(_format_financial_summary_section(doc, use_colors=use_colors, currency_symbol=currency_symbol))

    # Section 3: Line Items Detail
    sections.append(_format_line_items_section(doc.line_items, use_colors=use_colors, currency_symbol=currency_symbol))

    # Section 4: Financial Reconciliation Engine (Rule V01)
    sections.append(_format_reconciliation_section(doc.reconciliation, use_colors=use_colors, currency_symbol=currency_symbol))

    # Section 5 & 6: Validation Findings and Final Audit Summary
    sections.append(format_validation_summary(doc, use_colors=use_colors))

    return "\n".join(sections)
