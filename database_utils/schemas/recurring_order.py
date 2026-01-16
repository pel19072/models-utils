from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from .client import ClientOut
from enum import Enum


# Forward reference import
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .order import OrderOut


class RecurrenceEnum(str, Enum):
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"
    YEARLY = "YEARLY"


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
    is_active: Optional[bool] = None
    template_items: Optional[List[RecurringOrderItemInput]] = None


class RecurringOrderOut(RecurringOrderBase):
    id: int
    created_at: datetime
    company_id: int
    last_generated_at: Optional[datetime] = None
    next_generation_date: Optional[datetime] = None
    is_active: bool
    client: Optional[ClientOut]
    template_items: List[RecurringOrderItemOut]

    class ConfigDict:
        from_attributes = True


class OrderGenerationResponse(BaseModel):
    """Response when manually generating an order from a recurring template."""
    order: dict  # Use dict instead of OrderOut to avoid circular imports
    generation_for_date: datetime
    generation_period: str  # Human-readable period (e.g., "February 2026", "Week 7 2026")
    next_generation_date: Optional[datetime] = None

    class ConfigDict:
        from_attributes = True
