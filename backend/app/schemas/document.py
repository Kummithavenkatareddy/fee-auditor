from typing import Optional, List, Any, Dict
from pydantic import BaseModel, Field
from app.schemas.common import FieldStatus, ExtractedField, ExtractedLineItem, ValidationFlag
from app.schemas.invoice import InvoiceData
from app.schemas.receipt import ReceiptData


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

    # Common normalized view for UI and table rendering
    vendor_name: ExtractedField = Field(default_factory=ExtractedField)
    normalized_vendor_name: Optional[str] = None
    invoice_id: ExtractedField = Field(default_factory=ExtractedField)
    normalized_invoice_id: Optional[str] = None
    invoice_date: ExtractedField = Field(default_factory=ExtractedField)
    vendor_tax_id: ExtractedField = Field(default_factory=ExtractedField)
    subtotal: ExtractedField = Field(default_factory=ExtractedField)
    discounts: ExtractedField = Field(default_factory=ExtractedField)
    adjustments: ExtractedField = Field(default_factory=ExtractedField)
    tax: ExtractedField = Field(default_factory=ExtractedField)
    total: ExtractedField = Field(default_factory=ExtractedField)
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

    # Audit history & traceability
    audit_history: List[Dict[str, Any]] = Field(default_factory=list)
    raw_azure_json: Optional[str] = None
    normalized_json: Optional[str] = None


class BatchUploadResponse(BaseModel):
    batch_id: str
    total_files: int
    successful_extractions: int
    failed_extractions: int
    documents: List[DocumentExtraction]
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
