from typing import Optional
from pydantic import BaseModel
from datetime import datetime
from uuid import UUID


class InvoiceBase(BaseModel):
    issue_date: datetime
    subtotal: int
    tax: int
    total: int
    details: dict


class InvoiceCreate(InvoiceBase):
    order_id: UUID


class InvoiceUpdate(BaseModel):
    issue_date: Optional[datetime] = None
    subtotal: Optional[int] = None
    tax: Optional[int] = None
    total: Optional[int] = None
    details: Optional[dict] = None


class InvoiceOut(InvoiceBase):
    id: UUID
    created_at: datetime
    company_id: UUID
    order_id: UUID

    class ConfigDict:
        from_attributes = True
