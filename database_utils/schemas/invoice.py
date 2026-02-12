from typing import Optional
from pydantic import BaseModel, ConfigDict
from datetime import datetime
from uuid import UUID


class InvoiceBase(BaseModel):
    issue_date: datetime
    subtotal: float
    tax: float
    total: float
    details: dict


class InvoiceCreate(InvoiceBase):
    order_id: UUID


class InvoiceUpdate(BaseModel):
    issue_date: Optional[datetime] = None
    subtotal: Optional[float] = None
    tax: Optional[float] = None
    total: Optional[float] = None
    details: Optional[dict] = None


class InvoiceOut(InvoiceBase):
    id: UUID
    created_at: datetime
    company_id: UUID
    order_id: UUID
    is_valid: bool = True

    model_config = ConfigDict(from_attributes=True)
