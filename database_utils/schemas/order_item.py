from pydantic import BaseModel
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

class OrderItemOut(OrderItemBase):
    id: UUID
    product: Optional[ProductOut]

    class ConfigDict:
        from_attributes = True
