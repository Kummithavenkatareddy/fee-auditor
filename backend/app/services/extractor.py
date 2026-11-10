import hashlib
import json
import logging
import re
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from azure.ai.documentintelligence.models import AnalyzeResult

from app.schemas.common import (
    FieldStatus,
    ExtractedField,
    ExtractedLineItem,
    format_canonical_decimal,
    TaxBreakdown,
)
from app.schemas.invoice import InvoiceData
from app.schemas.receipt import ReceiptData
from app.schemas.document import DocumentExtraction
from app.services.azure_client import analyze_document_bytes

logger = logging.getLogger(__name__)


def compute_file_hash(content: bytes) -> str:
    """Compute SHA-256 binary hash for exact duplicate detection."""
    return hashlib.sha256(content).hexdigest()


def detect_content_type(filename: str) -> str:
    """Determine MIME content type from filename extension."""
    lower_name = filename.lower()
    if lower_name.endswith(".png"):
        return "image/png"
    elif lower_name.endswith((".jpg", ".jpeg")):
        return "image/jpeg"
    elif lower_name.endswith(".pdf"):
        return "application/pdf"
    return "application/octet-stream"


def _extract_canonical_currency(field: Any) -> Optional[str]:
    """Extract and format currency value as an exact canonical decimal string with 2 decimals."""
    if field is None:
        return None

    # 1. Check value_currency (dict or object)
    val_curr = getattr(field, "value_currency", None)
    if val_curr is not None:
        if isinstance(val_curr, dict):
            amt = val_curr.get("amount")
            if amt is not None:
                return format_canonical_decimal(amt)
        elif hasattr(val_curr, "amount") and val_curr.amount is not None:
            return format_canonical_decimal(val_curr.amount)

    # 2. Check value_number
    val_num = getattr(field, "value_number", None)
    if val_num is not None:
        return format_canonical_decimal(val_num)

    # 3. Clean raw content string
    content = getattr(field, "content", None)
    if content:
        return format_canonical_decimal(content)

    return None


SUPPORTED_DATE_FORMATS = (
    "%Y-%m-%d",
    "%d/%m/%Y",
    "%m/%d/%Y",
    "%d-%m-%Y",
    "%d %B %Y",
    "%d %b %Y",
    "%B %d, %Y",
    "%b %d, %Y",
    "%B %d %Y",
    "%b %d %Y",
    "%Y/%m/%d",
    "%m-%d-%Y",
)


def _extract_date_value(field: Any) -> Optional[str]:
    """Extract date in ISO format YYYY-MM-DD from Azure DocumentField or string."""
    if field is None:
        return None

    if isinstance(field, (date, datetime)):
        return field.strftime("%Y-%m-%d")

    if isinstance(field, str):
        content = field.strip()
    else:
        val_date = getattr(field, "value_date", None)
        if val_date is not None:
            if isinstance(val_date, (date, datetime)):
                return val_date.strftime("%Y-%m-%d")
            if isinstance(val_date, str):
                content = val_date.strip()
            else:
                content = None
        else:
            content = getattr(field, "content", None)
            if content:
                content = content.strip()
            else:
                content = None

    if not content:
        return None

    for fmt in SUPPORTED_DATE_FORMATS:
        try:
            return datetime.strptime(content, fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass

    return content


def _extract_string_value(field: Any) -> Optional[str]:
    """Extract stripped string value from Azure DocumentField."""
    if field is None:
        return None

    val_str = getattr(field, "value_string", None)
    if val_str is not None and str(val_str).strip():
        return str(val_str).strip()

    content = getattr(field, "content", None)
    if content is not None and str(content).strip():
        return str(content).strip()

    return None


def _extract_field_confidence(field: Any) -> Optional[float]:
    """Extract confidence score (0.0 to 1.0) from Azure DocumentField."""
    if field is None:
        return None
    conf = getattr(field, "confidence", None)
    if conf is not None:
        try:
            return round(float(conf), 4)
        except (ValueError, TypeError):
            return None
    return None


def _extract_field_content(field: Any) -> Optional[str]:
    """Extract raw recognized text content from Azure DocumentField."""
    if field is None:
        return None
    return getattr(field, "content", None)


def _build_field(
    field_obj: Any,
    field_type: str = "string",
    default_status: FieldStatus = FieldStatus.MISSING,
) -> ExtractedField:
    """Build an ExtractedField object preserving value, confidence, raw text, and status."""
    if field_obj is None:
        return ExtractedField(value=None, confidence=None, raw_text=None, status=default_status)

    confidence = _extract_field_confidence(field_obj)
    raw_text = _extract_field_content(field_obj)

    if field_type == "currency":
        value = _extract_canonical_currency(field_obj)
    elif field_type == "date":
        value = _extract_date_value(field_obj)
    else:
        value = _extract_string_value(field_obj)

    if value is None:
        status = default_status
    elif confidence is not None and confidence < 0.85:
        status = FieldStatus.LOW_CONFIDENCE
    else:
        status = FieldStatus.EXTRACTED

    return ExtractedField(value=value, confidence=confidence, raw_text=raw_text, status=status)


def _extract_line_items(items_field: Any, is_receipt: bool = False) -> List[ExtractedLineItem]:
    """Normalize line items from Azure DocumentField value_array."""
    items: List[ExtractedLineItem] = []
    if items_field is None:
        return items

    val_array = getattr(items_field, "value_array", None)
    if not val_array and isinstance(items_field, list):
        val_array = items_field

    if not val_array:
        return items

    for idx, item in enumerate(val_array):
        item_obj = getattr(item, "value_object", None)
        if item_obj is None and isinstance(item, dict):
            item_obj = item

        if not item_obj:
            continue

        desc_f = item_obj.get("Description") or item_obj.get("ProductCode")
        qty_f = item_obj.get("Quantity")

        if is_receipt:
            unit_p_f = item_obj.get("Price") or item_obj.get("UnitPrice")
            amt_f = item_obj.get("TotalPrice") or item_obj.get("Amount") or unit_p_f
        else:
            unit_p_f = item_obj.get("UnitPrice") or item_obj.get("Price")
            amt_f = item_obj.get("Amount") or item_obj.get("TotalPrice")

        desc = _extract_string_value(desc_f)
        qty = _extract_canonical_currency(qty_f)
        unit_p = _extract_canonical_currency(unit_p_f)
        amt = _extract_canonical_currency(amt_f)

        confidences = [
            _extract_field_confidence(f)
            for f in (desc_f, qty_f, unit_p_f, amt_f)
            if f is not None and _extract_field_confidence(f) is not None
        ]
        avg_conf = (
            round(sum(confidences) / len(confidences), 4) if confidences else None
        )

        items.append(
            ExtractedLineItem(
                item_index=idx,
                description=desc,
                quantity=qty,
                unit_price=unit_p,
                amount=amt,
                confidence=avg_conf,
            )
        )

    return items


def serialize_azure_result(result: AnalyzeResult) -> str:
    """Serialize the full Azure AnalyzeResult into a JSON string."""
    try:
        if hasattr(result, "as_dict"):
            return json.dumps(result.as_dict(), default=str)
        return json.dumps(dict(result), default=str)
    except Exception as exc:
        logger.warning("Failed to serialize AnalyzeResult: %s", str(exc))
        return "{}"


def _extract_tax_breakdown_and_adjustments(
    fields: Dict[str, Any],
    tax_field_obj: Any,
    content: Optional[str] = None,
) -> Tuple[
    ExtractedField,
    ExtractedField,
    ExtractedField,
    ExtractedField,
    ExtractedField,
    ExtractedField,
    TaxBreakdown,
    ExtractedField,
    ExtractedField,
    ExtractedField,
]:
    """Extract itemized taxes (CGST, SGST, IGST, Cess, other tax) and financial adjustments (discounts, additional charges, rounding)."""
    total_tax = _build_field(tax_field_obj, "currency", FieldStatus.NOT_APPLICABLE)
    cgst_f = ExtractedField(status=FieldStatus.NOT_APPLICABLE)
    sgst_f = ExtractedField(status=FieldStatus.NOT_APPLICABLE)
    igst_f = ExtractedField(status=FieldStatus.NOT_APPLICABLE)
    cess_f = ExtractedField(status=FieldStatus.NOT_APPLICABLE)
    other_tax_f = ExtractedField(status=FieldStatus.NOT_APPLICABLE)

    # 1. Parse structured TaxDetails / TaxItems from Azure
    tax_details_f = fields.get("TaxDetails") or fields.get("TaxItems")
    val_array = getattr(tax_details_f, "value_array", None)
    if not val_array and isinstance(tax_details_f, dict):
        val_array = tax_details_f.get("valueArray") or tax_details_f.get("value_array")
    if not val_array and isinstance(tax_details_f, list):
        val_array = tax_details_f

    if val_array:
        for item in val_array:
            item_obj = getattr(item, "value_object", None)
            if item_obj is None and isinstance(item, dict):
                item_obj = item.get("valueObject") or item.get("value_object") or item
            item_content = getattr(item, "content", None) or (item.get("content") if isinstance(item, dict) else "")

            amt_f = item_obj.get("Amount") if isinstance(item_obj, dict) else None
            amt = _extract_canonical_currency(amt_f)
            conf = _extract_field_confidence(amt_f)

            tax_cat = ""
            if isinstance(item_obj, dict):
                cat_f = item_obj.get("TaxCategory") or item_obj.get("Description") or item_obj.get("Rate")
                tax_cat = str(cat_f.get("valueString", "") if isinstance(cat_f, dict) else (getattr(cat_f, "value_string", "") or cat_f or ""))
            combined_text = f"{item_content} {tax_cat}".lower()

            if re.search(r"\b(?:cgst|central\s+gst)\b", combined_text) and amt:
                cgst_f = ExtractedField(value=amt, confidence=conf, raw_text=item_content, status=FieldStatus.EXTRACTED, confidence_source="azure")
            elif re.search(r"\b(?:sgst|utgst|state\s+gst)\b", combined_text) and amt:
                sgst_f = ExtractedField(value=amt, confidence=conf, raw_text=item_content, status=FieldStatus.EXTRACTED, confidence_source="azure")
            elif re.search(r"\b(?:igst|integrated\s+gst)\b", combined_text) and amt:
                igst_f = ExtractedField(value=amt, confidence=conf, raw_text=item_content, status=FieldStatus.EXTRACTED, confidence_source="azure")
            elif re.search(r"\b(?:cess|gst\s+cess)\b", combined_text) and amt:
                cess_f = ExtractedField(value=amt, confidence=conf, raw_text=item_content, status=FieldStatus.EXTRACTED, confidence_source="azure")
            elif amt:
                other_tax_f = ExtractedField(value=amt, confidence=conf, raw_text=item_content, status=FieldStatus.EXTRACTED, confidence_source="azure")

    # 2. Content regex fallback for itemized taxes (truthfully represented without fabricated Azure confidence)
    if content:
        if not cgst_f.value:
            m = re.search(r"(?:Central\s+GST|CGST)(?:\s*(?:@\s*\d+(?:\.\d+)?%|\(\s*(?:CGST\s*)?\d+(?:\.\d+)?%\s*\)))?[\s:#₹Rs\.]*([0-9,]+(?:\.[0-9]{1,2})?)", content, re.IGNORECASE)
            if m:
                cgst_f = ExtractedField(value=format_canonical_decimal(m.group(1)), confidence=None, raw_text=m.group(0), status=FieldStatus.EXTRACTED, confidence_source="ocr_fallback")
        if not sgst_f.value:
            m = re.search(r"(?:State\s+GST|UTGST|SGST)(?:\s*(?:@\s*\d+(?:\.\d+)?%|\(\s*(?:SGST\s*)?\d+(?:\.\d+)?%\s*\)))?[\s:#₹Rs\.]*([0-9,]+(?:\.[0-9]{1,2})?)", content, re.IGNORECASE)
            if m:
                sgst_f = ExtractedField(value=format_canonical_decimal(m.group(1)), confidence=None, raw_text=m.group(0), status=FieldStatus.EXTRACTED, confidence_source="ocr_fallback")
        if not igst_f.value:
            m = re.search(r"(?:Integrated\s+GST|IGST)(?:\s*(?:@\s*\d+(?:\.\d+)?%|\(\s*(?:IGST\s*)?\d+(?:\.\d+)?%\s*\)))?[\s:#₹Rs\.]*([0-9,]+(?:\.[0-9]{1,2})?)", content, re.IGNORECASE)
            if m:
                igst_f = ExtractedField(value=format_canonical_decimal(m.group(1)), confidence=None, raw_text=m.group(0), status=FieldStatus.EXTRACTED, confidence_source="ocr_fallback")
        if not cess_f.value:
            m = re.search(r"(?:GST\s+Cess|Cess)(?:\s*(?:@\s*\d+(?:\.\d+)?%|\(\s*\d+(?:\.\d+)?%\s*\)))?[\s:#₹Rs\.]*([0-9,]+(?:\.[0-9]{1,2})?)", content, re.IGNORECASE)
            if m:
                cess_f = ExtractedField(value=format_canonical_decimal(m.group(1)), confidence=None, raw_text=m.group(0), status=FieldStatus.EXTRACTED, confidence_source="ocr_fallback")

    # 3. Fallback for total_tax if missing from fields
    if not total_tax.value and content:
        m = re.search(r"(?:Total\s+Tax|Total\s+GST)[\s:#₹Rs\.]*([0-9,]+(?:\.[0-9]{1,2})?)", content, re.IGNORECASE)
        if m:
            total_tax = ExtractedField(value=format_canonical_decimal(m.group(1)), confidence=None, raw_text=m.group(0), status=FieldStatus.EXTRACTED, confidence_source="ocr_fallback")
    if not total_tax.value:
        itemized_dec_list = [f.as_decimal() for f in (cgst_f, sgst_f, igst_f, cess_f, other_tax_f) if f.value]
        if itemized_dec_list:
            total_tax = ExtractedField(value=f"{sum(itemized_dec_list):.2f}", confidence=None, raw_text=None, status=FieldStatus.EXTRACTED, confidence_source="ocr_fallback")

    # 4. Discounts
    disc_f = fields.get("TotalDiscount") or fields.get("Discount")
    discounts = _build_field(disc_f, "currency", FieldStatus.NOT_APPLICABLE)
    if not discounts.value and content:
        m = re.search(r"(?:Total\s+Discount|Trade\s+Discount|Discount)[\s:#₹Rs\.]*([0-9,]+(?:\.[0-9]{1,2})?)", content, re.IGNORECASE)
        if m:
            discounts = ExtractedField(value=format_canonical_decimal(m.group(1)), confidence=None, raw_text=m.group(0), status=FieldStatus.EXTRACTED, confidence_source="ocr_fallback")

    # 5. Additional charges (shipping / handling)
    ship_f = fields.get("ShippingCost") or fields.get("HandlingCost") or fields.get("AdditionalCharges")
    additional_charges = _build_field(ship_f, "currency", FieldStatus.NOT_APPLICABLE)
    if not additional_charges.value and content:
        m = re.search(r"(?:Shipping(?:\s*Charges?)?|Freight|Handling(?:\s*Charges?)?|Delivery(?:\s*Charges?)?|Additional\s+Charges?)[\s:#₹Rs\.]*([0-9,]+(?:\.[0-9]{1,2})?)", content, re.IGNORECASE)
        if m:
            additional_charges = ExtractedField(value=format_canonical_decimal(m.group(1)), confidence=None, raw_text=m.group(0), status=FieldStatus.EXTRACTED, confidence_source="ocr_fallback")

    # 6. Rounding adjustment
    round_f = fields.get("RoundingAdjustment") or fields.get("RoundOff")
    rounding_adjustment = _build_field(round_f, "currency", FieldStatus.NOT_APPLICABLE)
    if not rounding_adjustment.value and content:
        m = re.search(r"(?:Round(?:\s*Off)?|Rounding(?:\s*Adjustment)?)[\s:#₹Rs\.]*([+-]?[0-9,]+(?:\.[0-9]{1,2})?)", content, re.IGNORECASE)
        if m:
            rounding_adjustment = ExtractedField(value=format_canonical_decimal(m.group(1)), confidence=None, raw_text=m.group(0), status=FieldStatus.EXTRACTED, confidence_source="ocr_fallback")

    tax_breakdown = TaxBreakdown(
        cgst=cgst_f,
        sgst=sgst_f,
        igst=igst_f,
        cess=cess_f,
        other_tax=other_tax_f,
        total_tax=total_tax,
    )

    return (
        cgst_f,
        sgst_f,
        igst_f,
        cess_f,
        other_tax_f,
        total_tax,
        tax_breakdown,
        discounts,
        additional_charges,
        rounding_adjustment,
    )


def analyze_invoice_result(
    result: AnalyzeResult,
    file_bytes: bytes,
    filename: str = "invoice.pdf",
) -> DocumentExtraction:
    """Extract and normalize structured fields from prebuilt-invoice AnalyzeResult."""
    file_hash = compute_file_hash(file_bytes)
    raw_azure_json = serialize_azure_result(result)
    now_iso = datetime.now(timezone.utc).isoformat()

    if not result.documents or len(result.documents) == 0:
        return DocumentExtraction(
            file_name=filename,
            file_hash=file_hash,
            model_used="prebuilt-invoice",
            document_type="invoice",
            created_at=now_iso,
            raw_azure_json=raw_azure_json,
        )

    doc = result.documents[0]
    fields: Dict[str, Any] = doc.fields or {}

    # Map invoice fields explicitly
    vendor_f = fields.get("VendorName")
    tax_id_f = fields.get("VendorTaxId") or fields.get("TaxId")
    inv_id_f = fields.get("InvoiceId")
    date_f = fields.get("InvoiceDate")
    due_date_f = fields.get("DueDate")
    subtotal_f = fields.get("SubTotal") or fields.get("Subtotal")
    tax_f = fields.get("TotalTax") or fields.get("Tax")
    total_f = fields.get("InvoiceTotal") or fields.get("Total")
    items_f = fields.get("Items")
    cust_name_f = fields.get("CustomerName")

    vendor_name = _build_field(vendor_f, "string", FieldStatus.MISSING)

    # Deterministic fallback if prebuilt-invoice missed VendorName but OCR text is present
    if not vendor_name.value and getattr(result, "content", None):
        content_str = result.content
        candidate_name = None
        raw_v_text = None
        # 1. Look for explicit vendor/supplier/seller prefix
        v_match = re.search(r"(?:Vendor|Supplier|Seller|Sold\s*By|Merchant)[\s:#]+([^\n\r]+)", content_str, re.IGNORECASE)
        if v_match:
            candidate_name = v_match.group(1).strip()
            raw_v_text = v_match.group(0)
        else:
            # 2. Look for top header line before document type or section delimiters
            lines = [l.strip() for l in content_str.splitlines() if l.strip()]
            for line in lines[:5]:
                if re.search(r"\b(?:tax\s+invoice|commercial\s+invoice|invoice|bill\s+to|billed\s+to|customer|purchase\s+order)\b", line, re.IGNORECASE):
                    continue
                if re.search(r"^(?:plot|unit|shed|no\.|flat|street|road|floor|building|\d+)\b", line, re.IGNORECASE):
                    continue
                if len(line) >= 3 and not re.search(r"^\d+$", line):
                    candidate_name = line
                    raw_v_text = line
                    break

        if candidate_name:
            vendor_name = ExtractedField(
                value=candidate_name,
                confidence=None,  # Truthful representation: No fabricated Azure confidence
                raw_text=raw_v_text,
                status=FieldStatus.EXTRACTED,
                confidence_source="ocr_fallback",
            )

    vendor_tax_id = _build_field(tax_id_f, "string", FieldStatus.MISSING)

    # Fallback pattern extraction if prebuilt-invoice missed the tax label
    if not vendor_tax_id.value and getattr(result, "content", None):
        tax_match = re.search(r"(?:Tax\s*ID|EIN|VAT\s*ID|GSTIN)[\s:#]+([A-Za-z0-9-]+)", result.content, re.IGNORECASE)
        if tax_match:
            found_tax = tax_match.group(1).strip()
            vendor_tax_id = ExtractedField(
                value=found_tax,
                confidence=None,  # Truthful representation: No fabricated Azure confidence
                raw_text=tax_match.group(0),
                status=FieldStatus.EXTRACTED,
                confidence_source="ocr_fallback",
            )

    invoice_id = _build_field(inv_id_f, "string", FieldStatus.MISSING)
    invoice_date = _build_field(date_f, "date", FieldStatus.MISSING)
    due_date = _build_field(due_date_f, "date", FieldStatus.NOT_APPLICABLE)
    subtotal = _build_field(subtotal_f, "currency", FieldStatus.NOT_APPLICABLE)
    total = _build_field(total_f, "currency", FieldStatus.MISSING)
    customer_name = _build_field(cust_name_f, "string", FieldStatus.NOT_APPLICABLE)
    line_items = _extract_line_items(items_f, is_receipt=False)

    # Extract tax breakdown, GST components, discounts and adjustments
    (
        cgst,
        sgst,
        igst,
        cess,
        other_tax,
        tax,
        tax_breakdown,
        discounts,
        additional_charges,
        rounding_adjustment,
    ) = _extract_tax_breakdown_and_adjustments(fields, tax_f, getattr(result, "content", None))

    invoice_data = InvoiceData(
        vendor_name=vendor_name,
        vendor_tax_id=vendor_tax_id,
        vendor_address=ExtractedField(status=FieldStatus.NOT_APPLICABLE),
        customer_name=customer_name,
        invoice_id=invoice_id,
        invoice_date=invoice_date,
        due_date=due_date,
        subtotal=subtotal,
        cgst=cgst,
        sgst=sgst,
        igst=igst,
        cess=cess,
        other_tax=other_tax,
        discounts=discounts,
        additional_charges=additional_charges,
        rounding_adjustment=rounding_adjustment,
        tax=tax,
        total=total,
        line_items=line_items,
    )

    extraction = DocumentExtraction(
        file_name=filename,
        file_hash=file_hash,
        model_used="prebuilt-invoice",
        document_type="invoice",
        invoice_data=invoice_data,
        receipt_data=None,
        vendor_name=vendor_name,
        invoice_id=invoice_id,
        invoice_date=invoice_date,
        vendor_tax_id=vendor_tax_id,
        subtotal=subtotal,
        cgst=cgst,
        sgst=sgst,
        igst=igst,
        cess=cess,
        other_tax=other_tax,
        discounts=discounts,
        adjustments=additional_charges,
        additional_charges=additional_charges,
        rounding_adjustment=rounding_adjustment,
        tax=tax,
        total=total,
        tax_breakdown=tax_breakdown,
        line_items=line_items,
        created_at=now_iso,
        raw_azure_json=raw_azure_json,
    )
    extraction.normalized_json = json.dumps(
        extraction.model_dump(exclude={"raw_azure_json", "normalized_json"}),
        default=str,
    )
    return extraction


def analyze_receipt_result(
    result: AnalyzeResult,
    file_bytes: bytes,
    filename: str = "receipt.pdf",
) -> DocumentExtraction:
    """Extract and normalize structured fields from prebuilt-receipt AnalyzeResult."""
    file_hash = compute_file_hash(file_bytes)
    raw_azure_json = serialize_azure_result(result)
    now_iso = datetime.now(timezone.utc).isoformat()

    if not result.documents or len(result.documents) == 0:
        return DocumentExtraction(
            file_name=filename,
            file_hash=file_hash,
            model_used="prebuilt-receipt",
            document_type="receipt",
            created_at=now_iso,
            raw_azure_json=raw_azure_json,
        )

    doc = result.documents[0]
    fields: Dict[str, Any] = doc.fields or {}

    # Map receipt fields explicitly
    merchant_f = fields.get("MerchantName") or fields.get("VendorName")
    merchant_addr_f = fields.get("MerchantAddress")
    merchant_phone_f = fields.get("MerchantPhoneNumber")
    trans_date_f = fields.get("TransactionDate") or fields.get("InvoiceDate")
    trans_time_f = fields.get("TransactionTime")
    subtotal_f = fields.get("Subtotal") or fields.get("SubTotal")
    tax_f = fields.get("TotalTax") or fields.get("Tax")
    total_f = fields.get("Total") or fields.get("InvoiceTotal")
    items_f = fields.get("Items")

    merchant_name = _build_field(merchant_f, "string", FieldStatus.MISSING)
    merchant_addr = _build_field(merchant_addr_f, "string", FieldStatus.NOT_APPLICABLE)
    merchant_phone = _build_field(merchant_phone_f, "string", FieldStatus.NOT_APPLICABLE)
    trans_date = _build_field(trans_date_f, "date", FieldStatus.MISSING)
    trans_time = _build_field(trans_time_f, "string", FieldStatus.NOT_APPLICABLE)
    subtotal = _build_field(subtotal_f, "currency", FieldStatus.NOT_APPLICABLE)
    tax = _build_field(tax_f, "currency", FieldStatus.NOT_APPLICABLE)
    total = _build_field(total_f, "currency", FieldStatus.MISSING)
    line_items = _extract_line_items(items_f, is_receipt=True)

    # Fallback for date if Azure field missed it or extracted unparsed, but content has it
    if trans_date.value is None and hasattr(result, "content") and result.content:
        date_match = re.search(
            r"(?:Date|Dated)[\s:#]+([0-9]{1,4}[\s\-/][A-Za-z0-9\s\-/]+[0-9]{2,4})",
            result.content,
            re.IGNORECASE,
        )
        if date_match:
            parsed_d = _extract_date_value(date_match.group(1))
            if parsed_d:
                trans_date = ExtractedField(
                    value=parsed_d,
                    confidence=None,
                    raw_text=date_match.group(0),
                    status=FieldStatus.EXTRACTED,
                    confidence_source="ocr_fallback",
                )

    # Fallback for total: on educational fee receipts, Azure prebuilt-receipt often maps total to Subtotal
    if total.value is None:
        if subtotal.value is not None and (tax.value is None or tax.value in ("0.00", "0")):
            total = ExtractedField(
                value=subtotal.value,
                confidence=subtotal.confidence,
                raw_text=subtotal.raw_text,
                status=subtotal.status,
                confidence_source=subtotal.confidence_source,
            )
        elif hasattr(result, "content") and result.content:
            total_match = re.search(
                r"(?:Grand\s*Total|Total\s*Paid|Total\s*Amount|Total)[\s:#]+(?:₹|Rs\.?|\$)?\s*([\d,]+(?:\.\d{2})?)",
                result.content,
                re.IGNORECASE,
            )
            if total_match:
                total_val = format_canonical_decimal(total_match.group(1))
                if total_val:
                    total = ExtractedField(
                        value=total_val,
                        confidence=None,
                        raw_text=total_match.group(0),
                        status=FieldStatus.EXTRACTED,
                        confidence_source="ocr_fallback",
                    )

    # Tax ID is NOT APPLICABLE on standard retail/educational receipts
    tax_id = ExtractedField(value=None, confidence=None, raw_text=None, status=FieldStatus.NOT_APPLICABLE)

    # Invoice ID: Optional transaction or receipt number if available, else NOT_APPLICABLE
    receipt_id_field = (
        fields.get("ReceiptId")
        or fields.get("TransactionId")
        or fields.get("InvoiceId")
        or fields.get("ReceiptNumber")
    )
    receipt_id_val = _extract_string_value(receipt_id_field)
    receipt_conf = _extract_field_confidence(receipt_id_field)
    raw_receipt_text = _extract_field_content(receipt_id_field)

    if not receipt_id_val and hasattr(result, "content") and result.content:
        rec_match = re.search(
            r"(?:Receipt\s*(?:No\.?|Number|#)|Receipt\s*ID|Invoice\s*(?:No\.?|Number|#))[\s:#]+([A-Za-z0-9\-_/]+)",
            result.content,
            re.IGNORECASE,
        )
        if rec_match:
            receipt_id_val = rec_match.group(1).strip()
            receipt_conf = None
            raw_receipt_text = rec_match.group(0)

    invoice_id = ExtractedField(
        value=receipt_id_val,
        confidence=receipt_conf,
        raw_text=raw_receipt_text or receipt_id_val,
        status=FieldStatus.EXTRACTED if receipt_id_val else FieldStatus.NOT_APPLICABLE,
        confidence_source="azure" if receipt_conf is not None else ("ocr_fallback" if receipt_id_val else None),
    )

    # Extract tax breakdown, GST components, discounts and adjustments
    (
        cgst,
        sgst,
        igst,
        cess,
        other_tax,
        tax,
        tax_breakdown,
        discounts,
        additional_charges,
        rounding_adjustment,
    ) = _extract_tax_breakdown_and_adjustments(fields, tax_f, getattr(result, "content", None))

    receipt_data = ReceiptData(
        merchant_name=merchant_name,
        merchant_address=merchant_addr,
        merchant_phone_number=merchant_phone,
        transaction_date=trans_date,
        transaction_time=trans_time,
        subtotal=subtotal,
        tax=tax,
        total=total,
        items=line_items,
    )

    extraction = DocumentExtraction(
        file_name=filename,
        file_hash=file_hash,
        model_used="prebuilt-receipt",
        document_type="receipt",
        invoice_data=None,
        receipt_data=receipt_data,
        vendor_name=merchant_name,
        invoice_id=invoice_id,
        invoice_date=trans_date,
        vendor_tax_id=tax_id,
        subtotal=subtotal,
        cgst=cgst,
        sgst=sgst,
        igst=igst,
        cess=cess,
        other_tax=other_tax,
        discounts=discounts,
        adjustments=additional_charges,
        additional_charges=additional_charges,
        rounding_adjustment=rounding_adjustment,
        tax=tax,
        total=total,
        tax_breakdown=tax_breakdown,
        line_items=line_items,
        created_at=now_iso,
        raw_azure_json=raw_azure_json,
    )
    extraction.normalized_json = json.dumps(
        extraction.model_dump(exclude={"raw_azure_json", "normalized_json"}),
        default=str,
    )
    return extraction


def analyze_invoice(file_bytes: bytes, filename: str = "invoice.pdf") -> DocumentExtraction:
    """Analyze document using Azure prebuilt-invoice model."""
    content_type = detect_content_type(filename)
    logger.info("Calling Azure prebuilt-invoice for '%s'", filename)
    result = analyze_document_bytes(
        file_bytes=file_bytes,
        model_id="prebuilt-invoice",
        content_type=content_type,
    )
    return analyze_invoice_result(result=result, file_bytes=file_bytes, filename=filename)


def analyze_receipt(file_bytes: bytes, filename: str = "receipt.pdf") -> DocumentExtraction:
    """Analyze document using Azure prebuilt-receipt model."""
    content_type = detect_content_type(filename)
    logger.info("Calling Azure prebuilt-receipt for '%s'", filename)
    result = analyze_document_bytes(
        file_bytes=file_bytes,
        model_id="prebuilt-receipt",
        content_type=content_type,
    )
    return analyze_receipt_result(result=result, file_bytes=file_bytes, filename=filename)


def is_receipt_filename(filename: str) -> bool:
    """Check whether filename indicates a receipt document.

    Recognizes:
    - 'receipt' (case-insensitive substring)
    - 'REC-', 'REC_', 'rec-', 'rec_' (case-insensitive token at start or after separator)
    """
    if not filename:
        return False
    lower_name = filename.lower()
    if "receipt" in lower_name:
        return True
    return bool(re.search(r"(?:^|[_\-\s])rec[-_]", filename, re.IGNORECASE))


def determine_model(
    filename: str,
    preferred_model: Optional[str] = None,
    document_type: Optional[str] = None,
) -> str:
    """Determine whether to use 'prebuilt-receipt' or 'prebuilt-invoice'.

    Precedence order:
    1. Explicit preferred_model ('prebuilt-receipt' or 'prebuilt-invoice')
    2. Explicit document_type ('receipt' or 'invoice')
    3. Filename heuristics via is_receipt_filename (e.g. REC-003.pdf, rec_006.pdf)
    4. Default: 'prebuilt-invoice'
    """
    if preferred_model in ("prebuilt-receipt", "prebuilt-invoice"):
        return preferred_model

    if document_type:
        norm_type = document_type.strip().lower()
        if "receipt" in norm_type:
            return "prebuilt-receipt"
        elif "invoice" in norm_type:
            return "prebuilt-invoice"

    if is_receipt_filename(filename):
        return "prebuilt-receipt"

    return "prebuilt-invoice"


def extract_document(
    file_bytes: bytes,
    filename: str,
    preferred_model: Optional[str] = None,
    document_type: Optional[str] = None,
) -> DocumentExtraction:
    """Route document to appropriate Azure model (prebuilt-invoice or prebuilt-receipt)."""
    model = determine_model(
        filename=filename,
        preferred_model=preferred_model,
        document_type=document_type,
    )
    if model == "prebuilt-receipt":
        return analyze_receipt(file_bytes, filename)
    else:
        return analyze_invoice(file_bytes, filename)
