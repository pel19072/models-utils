from pydantic import BaseModel, ConfigDict
from typing import Optional
from uuid import UUID
from .product import ProductOut

class OrderItemBase(BaseModel):
    product_id: UUID
    quantity: int

class OrderItemInput(OrderItemBase):
    pass

class OrderItemCreate(OrderItemBase):
    pass

class OrderItemUpdate(BaseModel):
    product_id: Optional[UUID]
    quantity: Optional[int]

class OrderItemOut(BaseModel):
    id: UUID
    # Nullable since Cycle 1: product_id is SET NULL on product deletion; the
    # snapshot columns below keep the line meaningful (doc 16 §2.2).
    product_id: Optional[UUID] = None
    quantity: int
    product: Optional[ProductOut] = None
    # Order-time snapshots (nullable for pre-backfill history).
    unit_price_cents: Optional[int] = None
    product_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
