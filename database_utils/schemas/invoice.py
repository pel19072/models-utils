from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field
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


class BulkOrderIdsRequest(BaseModel):
    order_ids: List[UUID] = Field(..., min_length=1, max_length=100)


class BulkOperationItemResult(BaseModel):
    order_id: UUID
    success: bool
    invoice_id: Optional[UUID] = None
    error: Optional[str] = None


class BulkOperationResponse(BaseModel):
    succeeded: int
    failed: int
    results: List[BulkOperationItemResult]
