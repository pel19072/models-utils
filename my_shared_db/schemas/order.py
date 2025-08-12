from typing import List, Optional
from pydantic import BaseModel
from schemas.order_item import OrderItemInput, OrderItemOut

class OrderBase(BaseModel):
    client_id: Optional[int]

class OrderCreate(OrderBase):
    order_items: List[OrderItemInput]

class OrderUpdate(BaseModel):
    client_id: Optional[int]
    order_items: Optional[List[OrderItemInput]]

class OrderOut(OrderBase):
    id: int
    client_id: int
    company_id: int
    order_items: List[OrderItemOut]

    class Config:
        orm_mode = True
