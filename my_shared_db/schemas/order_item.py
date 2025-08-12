from pydantic import BaseModel
from typing import Optional

class OrderItemBase(BaseModel):
    product_id: int
    quantity: int

class OrderItemInput(OrderItemBase):
    pass

class OrderItemCreate(OrderItemBase):
    pass

class OrderItemUpdate(BaseModel):
    product_id: Optional[int]
    quantity: Optional[int]

class OrderItemOut(OrderItemBase):
    id: int

    class Config:
        orm_mode = True
