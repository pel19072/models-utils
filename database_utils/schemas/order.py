from typing import List, Optional
from pydantic import BaseModel
from .order_item import OrderItemInput, OrderItemOut
from .client import ClientOut

class OrderBase(BaseModel):
    client_id: Optional[int]

class OrderCreate(OrderBase):
    order_items: List[OrderItemInput]

class OrderUpdate(BaseModel):
    total: Optional[int] = None
    paid: Optional[bool] = None
    recurring: Optional[bool] = None
    recurrence: Optional[str] = None
    client_id: Optional[int] = None
    order_items: Optional[List[OrderItemInput]] = None

class OrderOut(OrderBase):
    id: int
    total: int
    paid: bool
    recurring: bool
    recurrence: Optional[str]
    client_id: int
    client: Optional[ClientOut]
    company_id: int
    order_items: List[OrderItemOut]

    class ConfigDict:
        from_attributes = True
