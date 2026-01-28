from typing import List, Optional, TYPE_CHECKING
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, computed_field, Field, ConfigDict
from .order_item import OrderItemInput, OrderItemOut
from .client import ClientOut
import calendar

if TYPE_CHECKING:
    from .recurring_order import RecurringOrderOut

class OrderBase(BaseModel):
    client_id: Optional[UUID]

class OrderCreate(OrderBase):
    order_items: List[OrderItemInput]
    due_date: Optional[datetime] = None  # Optional due date for manually created orders

class OrderUpdate(BaseModel):
    total: Optional[float] = None
    paid: Optional[bool] = None
    client_id: Optional[UUID] = None
    order_items: Optional[List[OrderItemInput]] = None
    due_date: Optional[datetime] = None

class OrderOut(OrderBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime
    due_date: Optional[datetime] = None
    payment_date: Optional[datetime] = None
    total: float
    paid: bool
    recurring_order_id: Optional[UUID] = None
    client_id: UUID
    client: Optional[ClientOut]
    company_id: UUID
    order_items: List[OrderItemOut]
    recurring_order: Optional["RecurringOrderOut"] = None

    @computed_field
    @property
    def generation_period(self) -> Optional[str]:
        """
        Compute a human-readable period label for recurring orders.
        Returns None if this is not a recurring order.
        Uses the due_date to determine the period.
        """
        if not self.recurring_order or not self.due_date:
            return None

        recurrence = self.recurring_order.recurrence
        # For recurring orders, the due_date represents the end of the billing period
        period_date = self.due_date

        if recurrence == "MONTHLY":
            return f"{calendar.month_name[period_date.month]} {period_date.year}"
        elif recurrence == "WEEKLY":
            week_num = period_date.isocalendar()[1]
            return f"Week {week_num} {period_date.year}"
        elif recurrence == "YEARLY":
            return f"{period_date.year}"
        elif recurrence == "DAILY":
            return period_date.strftime("%B %d, %Y")
        else:
            return period_date.strftime("%B %d, %Y")
