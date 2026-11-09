from decimal import Decimal, InvalidOperation
from datetime import datetime, date
from typing import List, Optional, Set, Dict, Any, Tuple
import re

from app.config import settings
from app.schemas.common import FieldStatus, format_canonical_decimal
from app.schemas.document import DocumentExtraction, ValidationFlag, ExtractedField


def _to_decimal(val: Any) -> Optional[Decimal]:
    """Safely convert any numeric, currency, or canonical decimal string to Decimal."""
    if val is None:
        return None
    try:
        if isinstance(val, Decimal):
            return val
        canonical = format_canonical_decimal(val)
        return Decimal(canonical) if canonical else None
    except (InvalidOperation, ValueError, TypeError):
        return None


SUPPORTED_DATE_FORMATS = (
    "%Y-%m-%d",      # 2026-08-01 (ISO)
    "%d/%m/%Y",      # 15/11/2026 (DD/MM/YYYY)
    "%m/%d/%Y",      # 11/15/2026 (MM/DD/YYYY)
    "%d-%m-%Y",      # 15-11-2026 (DD-MM-YYYY)
    "%d %B %Y",      # 15 November 2026 (DD Month YYYY)
    "%d %b %Y",      # 15 Nov 2026 (DD Mon YYYY)
    "%B %d, %Y",     # November 15, 2026 (Month DD, YYYY)
    "%b %d, %Y",     # Nov 15, 2026 (Mon DD, YYYY)
    "%B %d %Y",      # November 15 2026
    "%b %d %Y",      # Nov 15 2026
    "%Y/%m/%d",      # 2026/08/01
    "%m-%d-%Y",      # 11-15-2026
)


def _parse_iso_date(date_str: Optional[str]) -> Optional[date]:
    """Parse date string deterministically into date object supporting standard and natural formats."""
    if not date_str or not isinstance(date_str, str):
        return None
    cleaned = date_str.strip()
    for fmt in SUPPORTED_DATE_FORMATS:
        try:
            return datetime.strptime(cleaned, fmt).date()
        except ValueError:
            pass
    return None


def validate_v01_total_mismatch(doc: DocumentExtraction) -> Optional[ValidationFlag]:
    """V01 — Deterministic Financial Validation Engine:

    Reconciles line-item amounts, applicable taxes, discounts, and adjustments against stated totals.
    Uses Python Decimal arithmetic with currency rounding tolerance ($0.02).

    Deterministic Semantics:
    1. Explicit Tax-Exclusive:
       Line items sum reconciles to Subtotal (Net base). Expected Total = Subtotal - Discounts + Adjustments + Tax.
    2. Explicit Tax-Inclusive:
       Line items sum reconciles directly to Total (Gross charges). Subtotal is gross, or net base, or omitted.
    3. Partial Line-Item Extraction:
       If any item lacks an amount, emits V01 (HIGH severity) requiring manual review.
    4. Ambiguous Semantics:
       If line items neither sum to subtotal nor equal total, emits V01 (HIGH severity) manual review.
    Never blindly selects whichever equation happens to match.
    """
    total_dec = _to_decimal(doc.total.value)
    if total_dec is None:
        return ValidationFlag(
            rule_id="V01",
            rule_name="Total Missing / Invalid",
            severity="CRITICAL",
            field_name="total",
            reason="Document total amount is missing or cannot be parsed as a valid numeric decimal amount.",
            expected_value="Valid numeric monetary total",
            actual_value=str(doc.total.raw_text or "Missing"),
        )

    subtotal_dec = _to_decimal(doc.subtotal.value)
    tax_dec = _to_decimal(doc.tax.value) or Decimal("0.00")
    discount_dec = _to_decimal(doc.discounts.value) or Decimal("0.00")
    adjustment_dec = _to_decimal(doc.adjustments.value) or Decimal("0.00")

    tolerance = Decimal("0.02")

    # Check for Partial Line-Item Extraction
    if doc.line_items:
        missing_amount_items = [
            item for item in doc.line_items
            if item.amount is None or _to_decimal(item.amount) is None
        ]
        if missing_amount_items:
            valid_count = len(doc.line_items) - len(missing_amount_items)
            return ValidationFlag(
                rule_id="V01",
                rule_name="Partial Line-Item Extraction",
                severity="HIGH",
                field_name="line_items",
                reason=(
                    f"Document contains {len(doc.line_items)} line items, but {len(missing_amount_items)} "
                    f"item(s) lack a recognized numeric monetary amount. Line-item sum is incomplete and "
                    f"cannot be reliably reconciled against subtotal or total. Requires manual audit review."
                ),
                expected_value=f"Valid monetary amounts for all {len(doc.line_items)} line items",
                actual_value=f"{valid_count} of {len(doc.line_items)} items have amounts",
            )

    # Collect valid line item amounts
    line_item_amounts = [
        _to_decimal(item.amount)
        for item in doc.line_items
        if item.amount is not None and _to_decimal(item.amount) is not None
    ]

    # Case A: Complete line items are present
    if line_item_amounts:
        line_items_sum = sum(line_item_amounts, Decimal("0.00"))

        # 1. Deterministic Tax-Exclusive Check:
        # Line items sum matches subtotal (net base before discount/adjustment)
        expected_exclusive_total = (
            (subtotal_dec if subtotal_dec is not None else line_items_sum)
            - discount_dec
            + adjustment_dec
            + tax_dec
        )

        if subtotal_dec is not None and abs(line_items_sum - subtotal_dec) <= tolerance:
            if abs(expected_exclusive_total - total_dec) <= tolerance:
                return None  # Unambiguously clean Tax-Exclusive
        elif subtotal_dec is None and abs(line_items_sum - discount_dec + adjustment_dec + tax_dec - total_dec) <= tolerance:
            return None  # Unambiguously clean Tax-Exclusive (subtotal omitted)

        # 2. Deterministic Tax-Inclusive Check:
        # Line items sum directly equals Total (gross items incorporating tax)
        gross_reconciled = line_items_sum - discount_dec + adjustment_dec
        if abs(gross_reconciled - total_dec) <= tolerance:
            # Document evidence of tax-inclusive reporting:
            # Subtotal is omitted, OR subtotal equals gross total, OR subtotal + tax = total (net base printed)
            if (
                subtotal_dec is None
                or abs(subtotal_dec - total_dec) <= tolerance
                or abs(subtotal_dec + tax_dec - total_dec) <= tolerance
            ):
                return None  # Unambiguously clean Tax-Inclusive

        # 3. Discrepancy Resolution:
        # If line items sum equals subtotal, net base is verified, but total does not reconcile
        if subtotal_dec is not None and abs(line_items_sum - subtotal_dec) <= tolerance:
            diff = abs(total_dec - expected_exclusive_total)
            discounts_str = f" - Disc ${discount_dec:.2f}" if discount_dec else ""
            adj_str = f" + Adj ${adjustment_dec:.2f}" if adjustment_dec else ""
            return ValidationFlag(
                rule_id="V01",
                rule_name="Total Mismatch (Tax-Exclusive)",
                severity="CRITICAL",
                field_name="total",
                reason=(
                    f"Line items represent tax-exclusive charges (Sum: ${line_items_sum:.2f}, Subtotal: ${subtotal_dec:.2f}). "
                    f"Expected total (${expected_exclusive_total:.2f} = Base ${subtotal_dec:.2f}{discounts_str}{adj_str} + Tax ${tax_dec:.2f}) "
                    f"does not match stated total (${total_dec:.2f}). Discrepancy: ${diff:.2f}."
                ),
                expected_value=f"${expected_exclusive_total:.2f}",
                actual_value=f"${total_dec:.2f}",
            )

        # If subtotal was omitted but lines don't reconcile with total
        if subtotal_dec is None:
            expected_total = line_items_sum - discount_dec + adjustment_dec + tax_dec
            diff = abs(total_dec - expected_total)
            return ValidationFlag(
                rule_id="V01",
                rule_name="Total Mismatch",
                severity="CRITICAL",
                field_name="total",
                reason=(
                    f"Line items sum (${line_items_sum:.2f}) + Tax (${tax_dec:.2f}) = ${expected_total:.2f}, "
                    f"which does not match stated total (${total_dec:.2f}). Discrepancy: ${diff:.2f}."
                ),
                expected_value=f"${expected_total:.2f}",
                actual_value=f"${total_dec:.2f}",
            )

        # Otherwise: Line items do not sum to Subtotal AND do not equal Total -> Ambiguous / Reconciliation Failed
        sub_str = f"${subtotal_dec:.2f}" if subtotal_dec is not None else "None"
        return ValidationFlag(
            rule_id="V01",
            rule_name="Ambiguous Tax & Total Semantics",
            severity="HIGH",
            field_name="total",
            reason=(
                f"Financial reconciliation failed: The sum of {len(line_item_amounts)} line items "
                f"(${line_items_sum:.2f}) does not reconcile with either the extracted subtotal "
                f"({sub_str}) or stated total (${total_dec:.2f}) with tax (${tax_dec:.2f}). "
                f"Requires manual audit review."
            ),
            expected_value=f"Reconciled line sum (Subtotal: ${subtotal_dec or 'N/A'}, Total: ${total_dec:.2f})",
            actual_value=f"Line sum: ${line_items_sum:.2f}",
        )

    # Case B: No line items extracted, but Subtotal and Tax are present
    if subtotal_dec is not None:
        expected_total = subtotal_dec - discount_dec + adjustment_dec + tax_dec
        diff = abs(total_dec - expected_total)
        if diff > tolerance:
            return ValidationFlag(
                rule_id="V01",
                rule_name="Total Mismatch",
                severity="CRITICAL",
                field_name="total",
                reason=(
                    f"Subtotal (${subtotal_dec:.2f}) + Tax (${tax_dec:.2f}) = ${expected_total:.2f}, "
                    f"which does not match stated total (${total_dec:.2f}). Discrepancy: ${diff:.2f}."
                ),
                expected_value=f"${expected_total:.2f}",
                actual_value=f"${total_dec:.2f}",
            )
        return None

    # Case C: Neither line items nor subtotal available — Ambiguous calculation
    if tax_dec > Decimal("0.00"):
        return ValidationFlag(
            rule_id="V01",
            rule_name="Ambiguous Tax & Total Semantics",
            severity="HIGH",
            field_name="total",
            reason=(
                f"Document states tax of ${tax_dec:.2f} and total of ${total_dec:.2f}, but lacks "
                f"subtotal and itemized lines to verify if tax was added or included. Requires manual audit review."
            ),
            expected_value="Subtotal or line-item breakdown",
            actual_value=f"Total: ${total_dec:.2f}, Tax: ${tax_dec:.2f}",
        )

    return None


def validate_v02_missing_tax_number(doc: DocumentExtraction) -> Optional[ValidationFlag]:
    """V02 — Missing tax number:

    Flag missing or whitespace-only vendor tax identifiers on invoices.
    Receipts (doc_type == "receipt") are legally exempt and designated NOT_APPLICABLE.
    """
    if doc.document_type == "receipt":
        return None

    status = doc.vendor_tax_id.status
    if status == FieldStatus.NOT_APPLICABLE:
        return None

    tax_val = doc.vendor_tax_id.value
    if status == FieldStatus.MISSING or tax_val is None or not str(tax_val).strip():
        # Ensure status is marked MISSING for downstream consistency
        doc.vendor_tax_id.status = FieldStatus.MISSING
        return ValidationFlag(
            rule_id="V02",
            rule_name="Missing Tax Number",
            severity="MEDIUM",
            field_name="vendor_tax_id",
            reason="Vendor tax registration identifier (Tax ID, EIN, VAT, or GST) is missing from the invoice.",
            expected_value="Valid vendor tax registration number",
            actual_value="Missing / Not Detected",
        )
    return None


def validate_v03_duplicate_invoice(
    doc: DocumentExtraction,
    existing_hashes: Any,
    existing_business_keys: Dict[Tuple[str, str], str],
    existing_receipt_keys: Optional[Dict[Tuple[str, str, str], str]] = None,
) -> Optional[ValidationFlag]:
    """V03 — Two-Tier Duplicate Detection:

    Tier 1: Exact file duplicate via SHA-256 binary hash (applies to all document types).
            Label: 'Duplicate Document (Exact File)'.
    Tier 2: Business duplicate via normalized vendor name + normalized invoice ID (invoices only).
            Label: 'Duplicate Invoice (Business Identifier)'.
    Receipt Heuristic: Matching merchant, date, and total is treated as a heuristic warning,
                       NOT definitive proof of a duplicate transaction.
    """
    hashes_dict = existing_hashes if isinstance(existing_hashes, dict) else {h: "prior upload" for h in existing_hashes}

    # 1. Tier 1: Exact File Duplicate (Universal for all document types)
    if doc.file_hash in hashes_dict:
        doc.is_exact_duplicate = True
        doc.is_duplicate = True
        orig_file = hashes_dict[doc.file_hash]
        return ValidationFlag(
            rule_id="V03",
            rule_name="Duplicate Document (Exact File)",
            severity="CRITICAL",
            field_name="file_hash",
            reason=(
                f"Exact duplicate document detected. An identical file (SHA-256: {doc.file_hash[:10]}...) "
                f"matching original document '{orig_file}' has already been ingested and recorded in the audit database."
            ),
            expected_value="Unique file payload",
            actual_value=f"Identical SHA-256 matching '{orig_file}'",
        )

    # 2. Tier 2: Business Duplicate for Invoices (Normalized Vendor + Normalized Invoice ID)
    if doc.document_type == "invoice":
        v_val = doc.vendor_name.value
        inv_val = doc.invoice_id.value
        if v_val and inv_val:
            from app.db.repository import normalize_business_key

            b_key = normalize_business_key(v_val, inv_val)
            if b_key and b_key in existing_business_keys:
                prior_file = existing_business_keys[b_key]
                doc.is_business_duplicate = True
                doc.is_duplicate = True
                return ValidationFlag(
                    rule_id="V03",
                    rule_name="Duplicate Invoice (Business Identifier)",
                    severity="CRITICAL",
                    field_name="invoice_id",
                    reason=(
                        f"Business duplicate detected: Normalized vendor '{b_key[0]}' and invoice number "
                        f"'{b_key[1]}' match a previously registered document ('{prior_file}'). "
                        f"Potential duplicate billing claim across distinct file uploads."
                    ),
                    expected_value="Unique vendor invoice identifier",
                    actual_value=f"Duplicate invoice ID '{b_key[1]}' for vendor '{b_key[0]}'",
                )

    # 3. Receipt Heuristic (Merchant, Date, Total) — Non-definitive warning only
    if doc.document_type == "receipt" and existing_receipt_keys:
        from app.db.repository import normalize_receipt_key

        r_key = normalize_receipt_key(doc.vendor_name.value, doc.invoice_date.value, doc.total.value)
        if r_key and r_key in existing_receipt_keys:
            prior_file = existing_receipt_keys[r_key]
            # Crucial: Treat as heuristic, not definitive proof. Do NOT set is_duplicate = True
            return ValidationFlag(
                rule_id="V03",
                rule_name="Potential Duplicate Receipt (Heuristic Match)",
                severity="WARNING",
                field_name="total",
                reason=(
                    f"Heuristic receipt match: Merchant '{r_key[0]}', date '{r_key[1]}', and total "
                    f"'${r_key[2]}' match previously uploaded document '{prior_file}'. "
                    f"This indicates a possible duplicate submission or legitimate identical recurring charge; "
                    f"manual review is recommended."
                ),
                expected_value="Unique transaction",
                actual_value=f"Matches '{prior_file}' (Merchant: {r_key[0]}, Date: {r_key[1]}, Total: ${r_key[2]})",
            )

    return None


def validate_v04_outside_academic_term(
    doc: DocumentExtraction,
    term_start: Optional[date] = None,
    term_end: Optional[date] = None,
) -> Optional[ValidationFlag]:
    """V04 — Outside academic term & date validity:

    - An unparsable or missing date triggers manual review (HIGH severity).
    - A valid date outside inclusive academic term boundaries triggers OUTSIDE_ACADEMIC_TERM (MEDIUM severity).
    """
    start_d = term_start or _parse_iso_date(settings.ACADEMIC_TERM_START) or date(2026, 8, 1)
    end_d = term_end or _parse_iso_date(settings.ACADEMIC_TERM_END) or date(2026, 12, 31)

    inv_date_str = doc.invoice_date.value

    # Condition 1: Missing or unparsable date -> Manual review required
    if not inv_date_str or not str(inv_date_str).strip():
        return ValidationFlag(
            rule_id="V04",
            rule_name="Date Missing / Unparsable",
            severity="HIGH",
            field_name="invoice_date",
            reason=(
                f"Document date is missing or unextracted. Academic term compliance "
                f"({start_d.isoformat()} to {end_d.isoformat()}) cannot be determined deterministically. "
                f"Requires manual review."
            ),
            expected_value=f"Valid ISO date within {start_d.isoformat()} to {end_d.isoformat()}",
            actual_value="Missing",
        )

    parsed_date = _parse_iso_date(str(inv_date_str))
    if not parsed_date:
        return ValidationFlag(
            rule_id="V04",
            rule_name="Date Format Unrecognized",
            severity="HIGH",
            field_name="invoice_date",
            reason=(
                f"Document date string '{inv_date_str}' cannot be parsed into a standard calendar date. "
                f"Requires manual review to determine term compliance."
            ),
            expected_value=f"YYYY-MM-DD format ({start_d.isoformat()} to {end_d.isoformat()})",
            actual_value=str(inv_date_str),
        )

    # Condition 2: Valid date outside inclusive term boundaries
    if parsed_date < start_d or parsed_date > end_d:
        return ValidationFlag(
            rule_id="V04",
            rule_name="Outside Academic Term",
            severity="MEDIUM",
            field_name="invoice_date",
            reason=(
                f"Document date ({parsed_date.isoformat()}) falls outside the designated "
                f"academic term ({start_d.isoformat()} to {end_d.isoformat()})."
            ),
            expected_value=f"{start_d.isoformat()} to {end_d.isoformat()}",
            actual_value=parsed_date.isoformat(),
        )

    return None


def validate_v05_low_confidence(
    doc: DocumentExtraction,
    threshold: Optional[float] = None,
) -> List[ValidationFlag]:
    """V05 — Model-Scoped Low Confidence:

    Evaluates confidence per field against threshold (default: 0.85).
    Evaluates confidence ONLY for fields that were successfully extracted (status == EXTRACTED)
    and possess a valid numeric confidence score.
    Skips fields with MISSING or NOT_APPLICABLE status; a missing field never generates V05.
    """
    conf_thresh = threshold if threshold is not None else settings.CONFIDENCE_THRESHOLD
    flags: List[ValidationFlag] = []

    if doc.document_type == "receipt":
        fields_to_check = [
            ("vendor_name", "Merchant Name", doc.vendor_name),
            ("invoice_date", "Transaction Date", doc.invoice_date),
            ("total", "Total Amount", doc.total),
        ]
    else:
        fields_to_check = [
            ("vendor_name", "Vendor Name", doc.vendor_name),
            ("vendor_tax_id", "Vendor Tax ID", doc.vendor_tax_id),
            ("invoice_id", "Invoice Number", doc.invoice_id),
            ("invoice_date", "Invoice Date", doc.invoice_date),
            ("total", "Total Amount", doc.total),
        ]

    for field_key, field_label, field_obj in fields_to_check:
        # 1. Skip fields with MISSING or NOT_APPLICABLE status
        if field_obj.status in (FieldStatus.NOT_APPLICABLE, FieldStatus.MISSING):
            continue
        # 2. Skip if value is missing or empty string
        if field_obj.value is None or not str(field_obj.value).strip():
            continue
        # 3. Only evaluate if a numeric confidence score exists
        conf = field_obj.confidence
        if conf is not None and isinstance(conf, (int, float)) and conf < conf_thresh:
            flags.append(
                ValidationFlag(
                    rule_id="V05",
                    rule_name="Low Extraction Confidence",
                    severity="WARNING",
                    field_name=field_key,
                    reason=(
                        f"Extraction confidence for {field_label} is {conf:.1%}, "
                        f"which is below the required accuracy threshold of {conf_thresh:.1%}. "
                        f"Manual verification recommended."
                    ),
                    expected_value=f">= {conf_thresh:.2f}",
                    actual_value=f"{conf:.2f}",
                )
            )

    # Check individual line item confidences
    for idx, item in enumerate(doc.line_items):
        if item.confidence is not None and isinstance(item.confidence, (int, float)) and item.confidence < conf_thresh:
            flags.append(
                ValidationFlag(
                    rule_id="V05",
                    rule_name="Low Line Item Confidence",
                    severity="WARNING",
                    field_name=f"line_items[{idx}]",
                    reason=(
                        f"Average confidence for line item #{idx + 1} ('{item.description or 'Item'}') "
                        f"is {item.confidence:.1%}, below the threshold of {conf_thresh:.1%}. "
                        f"Manual verification recommended."
                    ),
                    expected_value=f">= {conf_thresh:.2f}",
                    actual_value=f"{item.confidence:.2f}",
                )
            )

    return flags


def apply_all_validation_rules(
    doc: DocumentExtraction,
    existing_hashes: Optional[Any] = None,
    existing_business_keys: Optional[Dict[Tuple[str, str], str]] = None,
    existing_receipt_keys: Optional[Dict[Tuple[str, str, str], str]] = None,
    term_start: Optional[date] = None,
    term_end: Optional[date] = None,
    confidence_threshold: Optional[float] = None,
) -> DocumentExtraction:
    """Run all deterministic validation rules (V01-V05) on extracted document."""
    from app.db.repository import normalize_vendor_name, normalize_invoice_id

    # Populate normalized fields separately
    doc.normalized_vendor_name = normalize_vendor_name(doc.vendor_name.value)
    doc.normalized_invoice_id = normalize_invoice_id(doc.invoice_id.value)

    hashes = existing_hashes or {}
    b_keys = existing_business_keys or {}
    r_keys = existing_receipt_keys or {}

    flags: List[ValidationFlag] = []

    # Rule V01 - Financial Calculation Policy
    v01 = validate_v01_total_mismatch(doc)
    if v01:
        flags.append(v01)

    # Rule V02 - Missing Tax Number (Invoices only)
    v02 = validate_v02_missing_tax_number(doc)
    if v02:
        flags.append(v02)

    # Rule V03 - Two-Tier Duplicate Detection & Receipt Heuristic
    v03 = validate_v03_duplicate_invoice(
        doc=doc,
        existing_hashes=hashes,
        existing_business_keys=b_keys,
        existing_receipt_keys=r_keys,
    )
    if v03:
        flags.append(v03)

    # Rule V04 - Inclusive Academic Term & Date Check
    v04 = validate_v04_outside_academic_term(doc, term_start, term_end)
    if v04:
        flags.append(v04)

    # Rule V05 - Model-Scoped Low Confidence (Extracted fields only)
    v05_list = validate_v05_low_confidence(doc, confidence_threshold)
    flags.extend(v05_list)

    doc.validation_flags = flags

    # Precedence: Calculate highest severity (CRITICAL > HIGH > MEDIUM > WARNING)
    severities = {f.severity for f in flags}
    if "CRITICAL" in severities:
        doc.highest_severity = "CRITICAL"
    elif "HIGH" in severities:
        doc.highest_severity = "HIGH"
    elif "MEDIUM" in severities:
        doc.highest_severity = "MEDIUM"
    elif "WARNING" in severities:
        doc.highest_severity = "WARNING"
    else:
        doc.highest_severity = None

    # Audit status precedence:
    # A pending manual review NEVER hides critical or other flags
    if doc.manual_review_status in ("approved", "rejected"):
        doc.audit_status = "reviewed"
    elif len(flags) > 0:
        doc.audit_status = "flagged"
    else:
        doc.audit_status = "clean"

    return doc
