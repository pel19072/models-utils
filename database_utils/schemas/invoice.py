from typing import Optional
from pydantic import BaseModel
from datetime import datetime


class InvoiceBase(BaseModel):
    issue_date: datetime
    subtotal: int
    tax: int
    total: int
    details: dict


class InvoiceCreate(InvoiceBase):
    order_id: int


class InvoiceUpdate(BaseModel):
    issue_date: Optional[datetime] = None
    subtotal: Optional[int] = None
    tax: Optional[int] = None
    total: Optional[int] = None
    details: Optional[dict] = None


class InvoiceOut(InvoiceBase):
    id: int
    created_at: datetime
    company_id: int
    order_id: int

    class ConfigDict:
        from_attributes = True
