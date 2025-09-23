from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from .client import ClientOut
from enum import Enum


class RecurrenceEnum(str, Enum):
    daily = "daily"
    weekly = "weekly"
    monthly = "monthly"
    yearly = "yearly"


# ===================== Items =====================
class RecurringOrderItemBase(BaseModel):
    product_id: int
    quantity: int


class RecurringOrderItemInput(RecurringOrderItemBase):
    pass


class RecurringOrderItemOut(RecurringOrderItemBase):
    id: int
    created_at: datetime

    class ConfigDict:
        from_attributes = True


# ===================== Orders =====================
class RecurringOrderBase(BaseModel):
    client_id: Optional[int]
    recurrence: RecurrenceEnum
    recurrence_end: Optional[datetime] = None


class RecurringOrderCreate(RecurringOrderBase):
    template_items: List[RecurringOrderItemInput]


class RecurringOrderUpdate(BaseModel):
    client_id: Optional[int] = None
    recurrence: Optional[RecurrenceEnum] = None
    recurrence_end: Optional[datetime] = None
    template_items: Optional[List[RecurringOrderItemInput]] = None


class RecurringOrderOut(RecurringOrderBase):
    id: int
    created_at: datetime
    company_id: int
    client: Optional[ClientOut]
    template_items: List[RecurringOrderItemOut]

    class ConfigDict:
        from_attributes = True
