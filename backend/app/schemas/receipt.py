from typing import List, Optional
from pydantic import BaseModel, Field
from app.schemas.common import ExtractedField, ExtractedLineItem


class ReceiptData(BaseModel):
    merchant_name: ExtractedField = Field(default_factory=ExtractedField)
    merchant_address: ExtractedField = Field(default_factory=ExtractedField)
    merchant_phone_number: ExtractedField = Field(default_factory=ExtractedField)
    transaction_date: ExtractedField = Field(default_factory=ExtractedField)
    transaction_time: ExtractedField = Field(default_factory=ExtractedField)
    subtotal: ExtractedField = Field(default_factory=ExtractedField)
    tax: ExtractedField = Field(default_factory=ExtractedField)
    total: ExtractedField = Field(default_factory=ExtractedField)
    items: List[ExtractedLineItem] = Field(default_factory=list)

