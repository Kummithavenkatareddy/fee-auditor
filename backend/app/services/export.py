import io
import csv
from typing import List, Optional

from app.schemas.document import DocumentExtraction
from app.db.repository import get_all_documents


def generate_audit_csv(documents: Optional[List[DocumentExtraction]] = None) -> bytes:
    """Generate a formatted CSV export of audit results."""
    if documents is None:
        documents = get_all_documents()

    fieldnames = [
        "Document ID",
        "File Name",
        "Document Type",
        "Vendor Name",
        "Vendor Confidence",
        "Invoice ID",
        "Invoice ID Confidence",
        "Invoice Date",
        "Date Confidence",
        "Vendor Tax ID",
        "Tax ID Confidence",
        "Subtotal",
        "Tax",
        "Total Amount",
        "Total Confidence",
        "Line Items Count",
        "Audit Status",
        "Validation Flags Count",
        "Flagged Rules",
        "Flag Details",
        "Manual Review Status",
        "Manual Review Notes",
        "Processed Date",
    ]

    rows = []
    for doc in documents:
        rule_ids = ", ".join(f.rule_id for f in doc.validation_flags)
        flag_details = " | ".join(
            f"[{f.rule_id}] {f.field_name or 'Doc'}: {f.reason}"
            for f in doc.validation_flags
        )

        rows.append(
            {
                "Document ID": doc.id,
                "File Name": doc.file_name,
                "Document Type": doc.document_type,
                "Vendor Name": doc.vendor_name.value or "",
                "Vendor Confidence": doc.vendor_name.confidence or "",
                "Invoice ID": doc.invoice_id.value or "",
                "Invoice ID Confidence": doc.invoice_id.confidence or "",
                "Invoice Date": doc.invoice_date.value or "",
                "Date Confidence": doc.invoice_date.confidence or "",
                "Vendor Tax ID": doc.vendor_tax_id.value or "",
                "Tax ID Confidence": doc.vendor_tax_id.confidence or "",
                "Subtotal": doc.subtotal.value if doc.subtotal.value is not None else "",
                "Tax": doc.tax.value if doc.tax.value is not None else "",
                "Total Amount": doc.total.value if doc.total.value is not None else "",
                "Total Confidence": doc.total.confidence or "",
                "Line Items Count": len(doc.line_items),
                "Audit Status": doc.audit_status,
                "Validation Flags Count": len(doc.validation_flags),
                "Flagged Rules": rule_ids or "None",
                "Flag Details": flag_details or "Compliant",
                "Manual Review Status": doc.manual_review_status or "pending",
                "Manual Review Notes": doc.manual_review_notes or "",
                "Processed Date": doc.created_at or "",
            }
        )

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames)
    writer.writeheader()
    if rows:
        writer.writerows(rows)
    return buf.getvalue().encode("utf-8")
