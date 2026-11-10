from typing import Optional, List, Any, Dict
from pydantic import BaseModel, Field
from app.schemas.common import (
    FieldStatus,
    ExtractedField,
    ExtractedLineItem,
    ValidationFlag,
    TaxBreakdown,
    FinancialReconciliation,
)
from app.schemas.invoice import InvoiceData
from app.schemas.receipt import ReceiptData


class ContentSafetyCategoryResult(BaseModel):
    category: str
    severity: int = 0
    threshold: int = 4
    flagged: bool = False


class ContentSafetyResult(BaseModel):
    is_safe: bool = True
    status: str = "passed"  # "passed", "rejected", "failed", "skipped"
    highest_severity: int = 0
    categories: List[ContentSafetyCategoryResult] = Field(default_factory=list)
    matched_custom_terms: List[str] = Field(default_factory=list)
    matched_blocklists: List[str] = Field(default_factory=list)
    action_taken: str = "accepted"  # "accepted", "rejected", "error"
    rejection_reason: Optional[str] = None
    details: Optional[str] = None


class ContentScreeningRejection(BaseModel):
    file_name: str
    status: str = "rejected"  # "rejected" or "failed"
    detected_category: Optional[str] = None
    severity: int = 0
    reason: str
    error_message: Optional[str] = None


class DocumentExtraction(BaseModel):
    id: Optional[str] = None
    file_name: str
    file_hash: str
    model_used: str = "prebuilt-invoice"
    document_type: str = "invoice"  # "invoice" or "receipt"
    extraction_status: str = "succeeded"  # "succeeded" or "failed"

    # Type-specific extraction models
    invoice_data: Optional[InvoiceData] = None
    receipt_data: Optional[ReceiptData] = None

    # Content Safety Screening metadata
    content_safety: Optional[ContentSafetyResult] = None
    content_safety_status: Optional[str] = "passed"

    # Common normalized view for UI and table rendering
    vendor_name: ExtractedField = Field(default_factory=ExtractedField)
    normalized_vendor_name: Optional[str] = None
    invoice_id: ExtractedField = Field(default_factory=ExtractedField)
    normalized_invoice_id: Optional[str] = None
    invoice_date: ExtractedField = Field(default_factory=ExtractedField)
    vendor_tax_id: ExtractedField = Field(default_factory=ExtractedField)
    subtotal: ExtractedField = Field(default_factory=ExtractedField)
    cgst: ExtractedField = Field(default_factory=ExtractedField)
    sgst: ExtractedField = Field(default_factory=ExtractedField)
    igst: ExtractedField = Field(default_factory=ExtractedField)
    cess: ExtractedField = Field(default_factory=ExtractedField)
    other_tax: ExtractedField = Field(default_factory=ExtractedField)
    discounts: ExtractedField = Field(default_factory=ExtractedField)
    adjustments: ExtractedField = Field(default_factory=ExtractedField)
    additional_charges: ExtractedField = Field(default_factory=ExtractedField)
    rounding_adjustment: ExtractedField = Field(default_factory=ExtractedField)
    tax: ExtractedField = Field(default_factory=ExtractedField)
    total: ExtractedField = Field(default_factory=ExtractedField)
    tax_breakdown: Optional[TaxBreakdown] = None
    reconciliation: Optional[FinancialReconciliation] = None
    line_items: List[ExtractedLineItem] = Field(default_factory=list)

    # Validation flags and compliance status
    validation_flags: List[ValidationFlag] = Field(default_factory=list)
    highest_severity: Optional[str] = None  # CRITICAL > HIGH > MEDIUM > WARNING
    is_exact_duplicate: bool = False
    is_business_duplicate: bool = False
    is_duplicate: bool = False
    audit_status: str = "clean"  # "clean", "flagged", "reviewed"
    manual_review_status: Optional[str] = "pending"  # "pending", "approved", "rejected"
    manual_review_notes: Optional[str] = None
    created_at: Optional[str] = None

    # Persistent library and ownership metadata
    owner_user_id: Optional[str] = "system_default"
    original_filename: Optional[str] = None
    storage_key: Optional[str] = None
    content_type: Optional[str] = None
    file_size: Optional[int] = None
    sha256_hash: Optional[str] = None
    uploaded_at: Optional[str] = None
    processing_status: Optional[str] = "completed"
    matched_document_id: Optional[str] = None
    matched_document_name: Optional[str] = None

    # Audit history & traceability
    audit_history: List[Dict[str, Any]] = Field(default_factory=list)
    raw_azure_json: Optional[str] = None
    normalized_json: Optional[str] = None


class DuplicateResponse(BaseModel):
    existing_document_id: str
    filename: str
    existing_file_name: Optional[str] = None
    document_type: str = "invoice"
    audit_status: str = "clean"
    upload_date: Optional[str] = None
    is_duplicate: bool = True
    is_exact_duplicate: bool = True
    duplicate_type: str = "exact"  # "exact" or "logical"
    message: str = "Exact file duplicate detected. Re-processing skipped to preserve original audit record."
    document_url: Optional[str] = None


class BatchUploadResponse(BaseModel):
    batch_id: str
    total_files: int
    successful_extractions: int
    duplicate_files: int = 0
    rejected_by_content_safety: int = 0
    screening_failed: int = 0
    failed_extractions: int
    documents: List[DocumentExtraction] = Field(default_factory=list)
    duplicates: List[DuplicateResponse] = Field(default_factory=list)
    rejected_documents: List[ContentScreeningRejection] = Field(default_factory=list)
    errors: List[dict] = Field(default_factory=list)


class ManualReviewUpdate(BaseModel):
    manual_review_status: str  # "approved", "rejected", "pending"
    notes: Optional[str] = None


class DashboardSummary(BaseModel):
    total_documents: int
    clean_documents: int
    flagged_documents: int
    pending_review_documents: int = 0
    total_value: float
    duplicate_count: int = 0
    low_confidence_documents: int = 0
    v01_count: int = 0
    v02_count: int = 0
    v03_count: int = 0
    v04_count: int = 0
    v05_count: int = 0
