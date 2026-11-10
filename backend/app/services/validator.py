from decimal import Decimal, InvalidOperation
from datetime import datetime, date
from typing import List, Optional, Set, Dict, Any, Tuple
import re

from app.config import settings
from app.schemas.common import FieldStatus, format_canonical_decimal, FinancialReconciliation
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
    """V01 — GST-Aware Deterministic Financial Reconciliation Engine:

    Reconciles line-item amounts, itemized GST components (CGST, SGST, IGST, Cess),
    aggregate taxes, invoice-level discounts, additional charges (shipping/handling),
    and rounding adjustments against stated totals.
    Uses Python Decimal arithmetic exclusively with currency rounding tolerance (₹0.02).

    Deterministic Accounting Principles:
    1. Line-item validation: When complete line items are present, line_items_sum
       reconciles against Subtotal (net taxable base), NOT grand total.
    2. Tax-exclusive grand total = Subtotal - Discounts + Charges + GST/Tax + Rounding.
       Prevents double-counting aggregate TotalTax when itemized GST components exist.
    3. Tax-inclusive grand total = Subtotal - Discounts + Charges + Rounding.
       Supports tax-inclusive structures without adding GST twice.
    4. Ambiguous structures (e.g. missing grand total, missing tax breakdown, partial lines)
       are flagged for manual audit review (HIGH severity) rather than false CRITICAL mismatches.
    5. Discrepancies exceeding ₹0.02 trigger a CRITICAL V01 Total Mismatch flag.
    Always records an authoritative FinancialReconciliation breakdown on doc.reconciliation.
    """
    tolerance = Decimal("0.02")

    total_dec = _to_decimal(doc.total.value) if doc.total else None
    subtotal_dec = _to_decimal(doc.subtotal.value) if doc.subtotal else None
    total_tax_dec = _to_decimal(doc.tax.value) if doc.tax and doc.tax.value is not None else Decimal("0.00")

    cgst_dec = _to_decimal(doc.cgst.value) if doc.cgst and doc.cgst.value is not None else None
    sgst_dec = _to_decimal(doc.sgst.value) if doc.sgst and doc.sgst.value is not None else None
    igst_dec = _to_decimal(doc.igst.value) if doc.igst and doc.igst.value is not None else None
    cess_dec = _to_decimal(doc.cess.value) if doc.cess and doc.cess.value is not None else None
    other_tax_dec = _to_decimal(doc.other_tax.value) if doc.other_tax and doc.other_tax.value is not None else None

    discounts_dec = _to_decimal(doc.discounts.value) if doc.discounts and doc.discounts.value is not None else Decimal("0.00")
    additional_charges_dec = (
        _to_decimal(doc.additional_charges.value) if doc.additional_charges and doc.additional_charges.value is not None
        else (_to_decimal(doc.adjustments.value) if doc.adjustments and doc.adjustments.value is not None else Decimal("0.00"))
    )
    rounding_dec = _to_decimal(doc.rounding_adjustment.value) if doc.rounding_adjustment and doc.rounding_adjustment.value is not None else Decimal("0.00")

    # Step 1: Missing / Unparsable Grand Total -> Manual Review (HIGH)
    if total_dec is None:
        doc.reconciliation = FinancialReconciliation(
            extracted_subtotal=f"{subtotal_dec:.2f}" if subtotal_dec is not None else None,
            total_tax=f"{total_tax_dec:.2f}" if total_tax_dec else None,
            extracted_grand_total=None,
            calculation_type="ambiguous",
            is_reconciled=False,
            status="MANUAL_REVIEW_REQUIRED",
            explanation="Grand total is missing or cannot be parsed as a valid numeric decimal amount. Requires manual audit review.",
        )
        return ValidationFlag(
            rule_id="V01",
            rule_name="Grand Total Missing / Invalid",
            severity="HIGH",
            field_name="total",
            reason="Document total amount is missing or cannot be parsed as a valid numeric decimal amount. Requires manual audit review.",
            expected_value="Valid numeric monetary total",
            actual_value=str(doc.total.raw_text or "Missing") if doc.total else "Missing",
        )

    # Step 2: Partial Line-Item Extraction Check
    if doc.line_items:
        missing_amount_items = [
            item for item in doc.line_items
            if item.amount is None or _to_decimal(item.amount) is None
        ]
        if missing_amount_items:
            valid_count = len(doc.line_items) - len(missing_amount_items)
            doc.reconciliation = FinancialReconciliation(
                extracted_subtotal=f"{subtotal_dec:.2f}" if subtotal_dec is not None else None,
                total_tax=f"{total_tax_dec:.2f}" if total_tax_dec else None,
                extracted_grand_total=f"{total_dec:.2f}",
                calculation_type="ambiguous",
                is_reconciled=False,
                status="MANUAL_REVIEW_REQUIRED",
                explanation=f"Incomplete line-item extraction ({len(missing_amount_items)} item(s) lack valid amount). Requires manual audit review.",
            )
            return ValidationFlag(
                rule_id="V01",
                rule_name="Partial Line-Item Extraction",
                severity="HIGH",
                field_name="line_items",
                reason=(
                    f"Document contains {len(doc.line_items)} line items, but {len(missing_amount_items)} "
                    f"item(s) lack a recognized numeric monetary amount. Line-item sum is incomplete and "
                    f"cannot be reliably reconciled against subtotal or grand total. Requires manual audit review."
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
    line_items_sum = sum(line_item_amounts, Decimal("0.00")) if line_item_amounts else None

    # Step 3: Line Items Sum vs Subtotal Check (Requirement 3A & Scenario 10)
    # When complete line items and subtotal are available, compare line_items_sum against subtotal, NOT grand total!
    if line_items_sum is not None and subtotal_dec is not None:
        line_sub_diff = abs(line_items_sum - subtotal_dec)
        if line_sub_diff > tolerance:
            doc.reconciliation = FinancialReconciliation(
                line_items_sum=f"{line_items_sum:.2f}",
                extracted_subtotal=f"{subtotal_dec:.2f}",
                cgst=f"{cgst_dec:.2f}" if cgst_dec is not None else None,
                sgst=f"{sgst_dec:.2f}" if sgst_dec is not None else None,
                igst=f"{igst_dec:.2f}" if igst_dec is not None else None,
                cess=f"{cess_dec:.2f}" if cess_dec is not None else None,
                other_tax=f"{other_tax_dec:.2f}" if other_tax_dec is not None else None,
                total_tax=f"{total_tax_dec:.2f}" if total_tax_dec else None,
                discounts=f"{discounts_dec:.2f}" if discounts_dec else None,
                additional_charges=f"{additional_charges_dec:.2f}" if additional_charges_dec else None,
                rounding_adjustment=f"{rounding_dec:.2f}" if rounding_dec else None,
                expected_grand_total=None,
                extracted_grand_total=f"{total_dec:.2f}",
                variance=f"{line_sub_diff:.2f}",
                calculation_type="tax_exclusive",
                is_reconciled=False,
                status="MANUAL_REVIEW_REQUIRED",
                explanation=f"Line items sum (${line_items_sum:.2f} / ₹{line_items_sum:.2f}) differs from stated subtotal (${subtotal_dec:.2f} / ₹{subtotal_dec:.2f}). Requires manual audit review.",
            )
            return ValidationFlag(
                rule_id="V01",
                rule_name="Line Items Mismatch",
                severity="HIGH",
                field_name="subtotal",
                reason=(
                    f"Sum of extracted line items (${line_items_sum:.2f} / ₹{line_items_sum:.2f}) does not match "
                    f"the declared subtotal (${subtotal_dec:.2f} / ₹{subtotal_dec:.2f}). Discrepancy: ${line_sub_diff:.2f} (₹{line_sub_diff:.2f}). Requires manual audit review."
                ),
                expected_value=f"₹{subtotal_dec:.2f}",
                actual_value=f"₹{line_items_sum:.2f}",
            )

    # Step 4: Determine Effective Tax (Prevent double-counting aggregate TotalTax if itemized GST exists)
    itemized_components = [c for c in (cgst_dec, sgst_dec, igst_dec, cess_dec, other_tax_dec) if c is not None]
    has_itemized_gst = any(c is not None for c in (cgst_dec, sgst_dec, igst_dec, cess_dec))

    if itemized_components:
        itemized_tax_sum = sum(itemized_components, Decimal("0.00"))
        if total_tax_dec > Decimal("0.00"):
            if abs(itemized_tax_sum - total_tax_dec) <= tolerance:
                effective_tax = total_tax_dec
            elif total_tax_dec > itemized_tax_sum:
                # Aggregate tax includes additional unspecified taxes
                unitemized_diff = total_tax_dec - itemized_tax_sum
                if other_tax_dec is None:
                    other_tax_dec = unitemized_diff
                effective_tax = total_tax_dec
            else:
                effective_tax = itemized_tax_sum
        else:
            effective_tax = itemized_tax_sum
    else:
        effective_tax = total_tax_dec

    # Step 5: Base taxable amount for reconciliation
    base_amount = subtotal_dec if subtotal_dec is not None else line_items_sum

    if base_amount is None:
        # Neither subtotal nor line items are available
        doc.reconciliation = FinancialReconciliation(
            extracted_subtotal=None,
            total_tax=f"{total_tax_dec:.2f}" if total_tax_dec else None,
            extracted_grand_total=f"{total_dec:.2f}",
            calculation_type="ambiguous",
            is_reconciled=False,
            status="MANUAL_REVIEW_REQUIRED",
            explanation="Missing subtotal and itemized line items. Requires manual audit review.",
        )
        return ValidationFlag(
            rule_id="V01",
            rule_name="Ambiguous Financial Structure",
            severity="HIGH",
            field_name="total",
            reason=(
                f"Document states grand total of ₹{total_dec:.2f} with tax ₹{effective_tax:.2f}, "
                f"but lacks subtotal and itemized lines to establish reconciliation. Requires manual audit review."
            ),
            expected_value="Subtotal or line-item breakdown",
            actual_value=f"Total: ₹{total_dec:.2f}, Tax: ₹{effective_tax:.2f}",
        )

    # Step 6: Evaluate Tax-Exclusive and Tax-Inclusive Reconciliation Formulas
    # Formula 1: Tax-Exclusive
    # Expected Grand Total = Subtotal - Discounts + Additional Charges + Effective Tax + Rounding
    expected_exclusive = base_amount - discounts_dec + additional_charges_dec + effective_tax + rounding_dec
    variance_exclusive = abs(total_dec - expected_exclusive)

    # Formula 2: Tax-Inclusive
    # Expected Grand Total = Subtotal - Discounts + Additional Charges + Rounding
    expected_inclusive = base_amount - discounts_dec + additional_charges_dec + rounding_dec
    variance_inclusive = abs(total_dec - expected_inclusive)

    # Case A: Tax-Exclusive Reconciled!
    if variance_exclusive <= tolerance:
        doc.reconciliation = FinancialReconciliation(
            line_items_sum=f"{line_items_sum:.2f}" if line_items_sum is not None else None,
            extracted_subtotal=f"{subtotal_dec:.2f}" if subtotal_dec is not None else None,
            cgst=f"{cgst_dec:.2f}" if cgst_dec is not None else None,
            sgst=f"{sgst_dec:.2f}" if sgst_dec is not None else None,
            igst=f"{igst_dec:.2f}" if igst_dec is not None else None,
            cess=f"{cess_dec:.2f}" if cess_dec is not None else None,
            other_tax=f"{other_tax_dec:.2f}" if other_tax_dec is not None else None,
            total_tax=f"{total_tax_dec:.2f}" if total_tax_dec > Decimal("0.00") or has_itemized_gst else None,
            effective_tax=f"{effective_tax:.2f}" if effective_tax > Decimal("0.00") else None,
            discounts=f"{discounts_dec:.2f}" if discounts_dec > Decimal("0.00") else None,
            additional_charges=f"{additional_charges_dec:.2f}" if additional_charges_dec > Decimal("0.00") else None,
            rounding_adjustment=f"{rounding_dec:.2f}" if rounding_dec != Decimal("0.00") else None,
            expected_grand_total=f"{expected_exclusive:.2f}",
            extracted_grand_total=f"{total_dec:.2f}",
            variance=f"{variance_exclusive:.2f}",
            calculation_type="tax_exclusive",
            is_reconciled=True,
            status="RECONCILED",
            explanation="Tax-exclusive financial reconciliation verified within ₹0.02 tolerance.",
        )
        return None

    # Case B: Tax-Inclusive Reconciled!
    if variance_inclusive <= tolerance:
        doc.reconciliation = FinancialReconciliation(
            line_items_sum=f"{line_items_sum:.2f}" if line_items_sum is not None else None,
            extracted_subtotal=f"{subtotal_dec:.2f}" if subtotal_dec is not None else None,
            cgst=f"{cgst_dec:.2f}" if cgst_dec is not None else None,
            sgst=f"{sgst_dec:.2f}" if sgst_dec is not None else None,
            igst=f"{igst_dec:.2f}" if igst_dec is not None else None,
            cess=f"{cess_dec:.2f}" if cess_dec is not None else None,
            other_tax=f"{other_tax_dec:.2f}" if other_tax_dec is not None else None,
            total_tax=f"{total_tax_dec:.2f}" if total_tax_dec > Decimal("0.00") or has_itemized_gst else None,
            effective_tax=f"{effective_tax:.2f}" if effective_tax > Decimal("0.00") else None,
            discounts=f"{discounts_dec:.2f}" if discounts_dec > Decimal("0.00") else None,
            additional_charges=f"{additional_charges_dec:.2f}" if additional_charges_dec > Decimal("0.00") else None,
            rounding_adjustment=f"{rounding_dec:.2f}" if rounding_dec != Decimal("0.00") else None,
            expected_grand_total=f"{expected_inclusive:.2f}",
            extracted_grand_total=f"{total_dec:.2f}",
            variance=f"{variance_inclusive:.2f}",
            calculation_type="tax_inclusive",
            is_reconciled=True,
            status="RECONCILED",
            explanation="Tax-inclusive financial reconciliation verified without double-counting tax.",
        )
        return None

    # Case C: Missing Tax Information -> Manual Review (HIGH severity, Scenario 11)
    # When tax was not provided / missing, and subtotal doesn't equal total
    if effective_tax == Decimal("0.00") and (doc.tax.value is None or doc.tax.status == FieldStatus.MISSING):
        doc.reconciliation = FinancialReconciliation(
            line_items_sum=f"{line_items_sum:.2f}" if line_items_sum is not None else None,
            extracted_subtotal=f"{subtotal_dec:.2f}" if subtotal_dec is not None else None,
            total_tax=None,
            expected_grand_total=f"{expected_exclusive:.2f}",
            extracted_grand_total=f"{total_dec:.2f}",
            variance=f"{variance_exclusive:.2f}",
            calculation_type="ambiguous",
            is_reconciled=False,
            status="MANUAL_REVIEW_REQUIRED",
            explanation="Tax information is missing and reconciliation cannot be established without guessing. Requires manual audit review.",
        )
        return ValidationFlag(
            rule_id="V01",
            rule_name="Missing Tax Information",
            severity="HIGH",
            field_name="tax",
            reason=(
                f"Subtotal (₹{base_amount:.2f}) does not reconcile with stated grand total (₹{total_dec:.2f}), "
                f"and applicable tax breakdown is missing. Reconciliation cannot be established without guessing. Requires manual audit review."
            ),
            expected_value=f"Applicable tax breakdown covering discrepancy of ₹{abs(total_dec - base_amount):.2f}",
            actual_value="Missing",
        )

    # Case D: Genuine Financial Mismatch (CRITICAL severity, Scenario 4 & 15)
    doc.reconciliation = FinancialReconciliation(
        line_items_sum=f"{line_items_sum:.2f}" if line_items_sum is not None else None,
        extracted_subtotal=f"{subtotal_dec:.2f}" if subtotal_dec is not None else None,
        cgst=f"{cgst_dec:.2f}" if cgst_dec is not None else None,
        sgst=f"{sgst_dec:.2f}" if sgst_dec is not None else None,
        igst=f"{igst_dec:.2f}" if igst_dec is not None else None,
        cess=f"{cess_dec:.2f}" if cess_dec is not None else None,
        other_tax=f"{other_tax_dec:.2f}" if other_tax_dec is not None else None,
        total_tax=f"{total_tax_dec:.2f}" if total_tax_dec > Decimal("0.00") or has_itemized_gst else None,
        effective_tax=f"{effective_tax:.2f}" if effective_tax > Decimal("0.00") else None,
        discounts=f"{discounts_dec:.2f}" if discounts_dec > Decimal("0.00") else None,
        additional_charges=f"{additional_charges_dec:.2f}" if additional_charges_dec > Decimal("0.00") else None,
        rounding_adjustment=f"{rounding_dec:.2f}" if rounding_dec != Decimal("0.00") else None,
        expected_grand_total=f"{expected_exclusive:.2f}",
        extracted_grand_total=f"{total_dec:.2f}",
        variance=f"{variance_exclusive:.2f}",
        calculation_type="tax_exclusive",
        is_reconciled=False,
        status="MISMATCH",
        explanation=f"Expected total of ₹{expected_exclusive:.2f} does not match stated total of ₹{total_dec:.2f}. Discrepancy: ₹{variance_exclusive:.2f}.",
    )

    discounts_str = f" - Disc ₹{discounts_dec:.2f}" if discounts_dec else ""
    charges_str = f" + Charges ₹{additional_charges_dec:.2f}" if additional_charges_dec else ""
    tax_str = f" + Tax ₹{effective_tax:.2f}" if effective_tax else ""
    round_str = f" + Rounding ₹{rounding_dec:.2f}" if rounding_dec else ""

    return ValidationFlag(
        rule_id="V01",
        rule_name="Total Mismatch",
        severity="CRITICAL",
        field_name="total",
        reason=(
            f"Expected total (${expected_exclusive:.2f} / ₹{expected_exclusive:.2f} = Base ${base_amount:.2f} / ₹{base_amount:.2f}"
            f"{discounts_str}{charges_str}{tax_str}{round_str}) "
            f"does not match stated total (${total_dec:.2f} / ₹{total_dec:.2f}). Discrepancy: ${variance_exclusive:.2f} (₹{variance_exclusive:.2f})."
        ),
        expected_value=f"${expected_exclusive:.2f}",
        actual_value=f"${total_dec:.2f}",
    )


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
                entry = existing_business_keys[b_key]
                if isinstance(entry, dict):
                    prior_file = entry.get("file_name", "prior upload")
                    prior_id = entry.get("id")
                    prior_type = entry.get("document_type", "invoice")
                else:
                    prior_file = str(entry)
                    prior_id = None
                    prior_type = "invoice"

                # Check document type matches
                if prior_type == "invoice":
                    doc.is_business_duplicate = True
                    doc.is_duplicate = True
                    if prior_id:
                        doc.matched_document_id = prior_id
                    doc.matched_document_name = prior_file

                    id_ref = f" (Document ID: {prior_id})" if prior_id else ""
                    return ValidationFlag(
                        rule_id="V03",
                        rule_name="Duplicate Invoice (Business Identifier)",
                        severity="CRITICAL",
                        field_name="invoice_id",
                        matched_document_id=prior_id,
                        reason=(
                            f"Business duplicate detected: Normalized vendor '{b_key[0]}' and invoice number "
                            f"'{b_key[1]}' match a previously registered document ('{prior_file}'{id_ref}). "
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
            entry = existing_receipt_keys[r_key]
            if isinstance(entry, dict):
                prior_file = entry.get("file_name", "prior upload")
                prior_id = entry.get("id")
                prior_type = entry.get("document_type", "receipt")
            else:
                prior_file = str(entry)
                prior_id = None
                prior_type = "receipt"

            if prior_type == "receipt":
                if prior_id:
                    doc.matched_document_id = prior_id
                doc.matched_document_name = prior_file

                id_ref = f" (Document ID: {prior_id})" if prior_id else ""
                # Crucial: Treat as heuristic, not definitive proof. Do NOT set is_duplicate = True
                return ValidationFlag(
                    rule_id="V03",
                    rule_name="Potential Duplicate Receipt (Heuristic Match)",
                    severity="WARNING",
                    field_name="total",
                    matched_document_id=prior_id,
                    reason=(
                        f"Heuristic receipt match: Merchant '{r_key[0]}', date '{r_key[1]}', and total "
                        f"'₹{r_key[2]}' match previously uploaded document '{prior_file}'{id_ref}. "
                        f"This indicates a possible duplicate submission or legitimate identical recurring charge; "
                        f"manual review is recommended."
                    ),
                    expected_value="Unique transaction",
                    actual_value=f"Matches '{prior_file}' (Merchant: {r_key[0]}, Date: {r_key[1]}, Total: ₹{r_key[2]})",
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
