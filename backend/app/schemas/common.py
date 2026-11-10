from enum import Enum
from typing import Optional, Any
from decimal import Decimal, InvalidOperation
from datetime import datetime, timezone
import re
from pydantic import BaseModel, Field


class FieldStatus(str, Enum):
    EXTRACTED = "extracted"
    MISSING = "missing"
    NOT_APPLICABLE = "not_applicable"
    LOW_CONFIDENCE = "low_confidence"


def format_canonical_decimal(val: Any) -> Optional[str]:
    """Format any numeric input into an exact canonical decimal string with 2 decimal places."""
    if val is None:
        return None
    try:
        if isinstance(val, Decimal):
            return f"{val:.2f}"
        if isinstance(val, (int, float)):
            return f"{Decimal(str(val)):.2f}"
        clean = re.sub(r"[^\d.-]", "", str(val).strip())
        if not clean or clean == "-":
            return None
        return f"{Decimal(clean):.2f}"
    except (InvalidOperation, ValueError, TypeError):
        return None


class ExtractedField(BaseModel):
    value: Optional[Any] = None
    confidence: Optional[float] = None
    raw_text: Optional[str] = None
    status: FieldStatus = FieldStatus.EXTRACTED
    confidence_source: Optional[str] = "azure"

    def as_decimal(self) -> Optional[Decimal]:
        """Convert value to Python Decimal."""
        if self.value is None:
            return None
        try:
            canonical = format_canonical_decimal(self.value)
            return Decimal(canonical) if canonical else None
        except Exception:
            return None


class ExtractedLineItem(BaseModel):
    item_index: Optional[int] = None
    description: Optional[str] = None
    quantity: Optional[str] = None  # Canonical decimal string e.g. "1.00"
    unit_price: Optional[str] = None  # Canonical decimal string e.g. "120.00"
    amount: Optional[str] = None  # Canonical decimal string e.g. "120.00"
    confidence: Optional[float] = None

    def amount_as_decimal(self) -> Optional[Decimal]:
        if self.amount is None:
            return None
        try:
            return Decimal(self.amount)
        except Exception:
            return None

    def unit_price_as_decimal(self) -> Optional[Decimal]:
        if self.unit_price is None:
            return None
        try:
            return Decimal(self.unit_price)
        except Exception:
            return None

    def quantity_as_decimal(self) -> Optional[Decimal]:
        if self.quantity is None:
            return None
        try:
            return Decimal(self.quantity)
        except Exception:
            return None


class ValidationFlag(BaseModel):
    rule_id: str = Field(..., description="V01, V02, V03, V04, or V05")
    rule_name: str
    severity: str = Field(..., description="CRITICAL, HIGH, MEDIUM, LOW, WARNING")
    field_name: Optional[str] = None
    reason: str
    expected_value: Optional[str] = None
    actual_value: Optional[str] = None
    matched_document_id: Optional[str] = None
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class TaxBreakdown(BaseModel):
    cgst: ExtractedField = Field(default_factory=ExtractedField)
    sgst: ExtractedField = Field(default_factory=ExtractedField)
    igst: ExtractedField = Field(default_factory=ExtractedField)
    cess: ExtractedField = Field(default_factory=ExtractedField)
    other_tax: ExtractedField = Field(default_factory=ExtractedField)
    total_tax: ExtractedField = Field(default_factory=ExtractedField)


class FinancialReconciliation(BaseModel):
    line_items_sum: Optional[str] = None
    extracted_subtotal: Optional[str] = None
    cgst: Optional[str] = None
    sgst: Optional[str] = None
    igst: Optional[str] = None
    cess: Optional[str] = None
    other_tax: Optional[str] = None
    total_tax: Optional[str] = None
    effective_tax: Optional[str] = None
    discounts: Optional[str] = None
    additional_charges: Optional[str] = None
    rounding_adjustment: Optional[str] = None
    expected_grand_total: Optional[str] = None
    extracted_grand_total: Optional[str] = None
    variance: Optional[str] = None
    calculation_type: str = "tax_exclusive"  # "tax_exclusive", "tax_inclusive", "ambiguous"
    is_reconciled: bool = True
    status: str = "RECONCILED"  # "RECONCILED", "MISMATCH", "MANUAL_REVIEW_REQUIRED"
    explanation: str = "Reconciled — No V01 flag."

