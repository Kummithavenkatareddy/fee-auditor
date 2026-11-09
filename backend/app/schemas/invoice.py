from typing import List, Optional
from pydantic import BaseModel, Field
from app.schemas.common import ExtractedField, ExtractedLineItem


class InvoiceData(BaseModel):
    vendor_name: ExtractedField = Field(default_factory=ExtractedField)
    vendor_tax_id: ExtractedField = Field(default_factory=ExtractedField)
    vendor_address: ExtractedField = Field(default_factory=ExtractedField)
    customer_name: ExtractedField = Field(default_factory=ExtractedField)
    invoice_id: ExtractedField = Field(default_factory=ExtractedField)
    invoice_date: ExtractedField = Field(default_factory=ExtractedField)
    due_date: ExtractedField = Field(default_factory=ExtractedField)
    subtotal: ExtractedField = Field(default_factory=ExtractedField)
    tax: ExtractedField = Field(default_factory=ExtractedField)
    total: ExtractedField = Field(default_factory=ExtractedField)
    line_items: List[ExtractedLineItem] = Field(default_factory=list)

