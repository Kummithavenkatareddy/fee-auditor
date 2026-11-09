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
    vendor_tax_id = _build_field(tax_id_f, "string", FieldStatus.MISSING)

    # Fallback pattern extraction if prebuilt-invoice missed the tax label
    if not vendor_tax_id.value and getattr(result, "content", None):
        tax_match = re.search(r"(?:Tax\s*ID|EIN|VAT\s*ID)[\s:#]+([A-Za-z0-9-]+)", result.content, re.IGNORECASE)
        if tax_match:
            found_tax = tax_match.group(1).strip()
            vendor_tax_id = ExtractedField(
                value=found_tax,
                confidence=0.90,
                raw_text=tax_match.group(0),
                status=FieldStatus.EXTRACTED,
            )

    invoice_id = _build_field(inv_id_f, "string", FieldStatus.MISSING)
    invoice_date = _build_field(date_f, "date", FieldStatus.MISSING)
    due_date = _build_field(due_date_f, "date", FieldStatus.NOT_APPLICABLE)
    subtotal = _build_field(subtotal_f, "currency", FieldStatus.NOT_APPLICABLE)
    tax = _build_field(tax_f, "currency", FieldStatus.NOT_APPLICABLE)
    total = _build_field(total_f, "currency", FieldStatus.MISSING)
    customer_name = _build_field(cust_name_f, "string", FieldStatus.NOT_APPLICABLE)
    line_items = _extract_line_items(items_f, is_receipt=False)

    invoice_data = InvoiceData(
        vendor_name=vendor_name,
        vendor_tax_id=vendor_tax_id,
        vendor_address=ExtractedField(status=FieldStatus.NOT_APPLICABLE),
        customer_name=customer_name,
        invoice_id=invoice_id,
        invoice_date=invoice_date,
        due_date=due_date,
        subtotal=subtotal,
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
        tax=tax,
        total=total,
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
                    confidence=0.88,
                    raw_text=date_match.group(0),
                    status=FieldStatus.EXTRACTED,
                )

    # Fallback for total: on educational fee receipts, Azure prebuilt-receipt often maps total to Subtotal
    if total.value is None:
        if subtotal.value is not None and (tax.value is None or tax.value in ("0.00", "0")):
            total = ExtractedField(
                value=subtotal.value,
                confidence=subtotal.confidence,
                raw_text=subtotal.raw_text,
                status=FieldStatus.EXTRACTED,
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
                        confidence=0.88,
                        raw_text=total_match.group(0),
                        status=FieldStatus.EXTRACTED,
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
            receipt_conf = 0.88
            raw_receipt_text = rec_match.group(0)

    invoice_id = ExtractedField(
        value=receipt_id_val,
        confidence=receipt_conf or (0.90 if receipt_id_val else None),
        raw_text=raw_receipt_text or receipt_id_val,
        status=FieldStatus.EXTRACTED if receipt_id_val else FieldStatus.NOT_APPLICABLE,
    )

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
        tax=tax,
        total=total,
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
