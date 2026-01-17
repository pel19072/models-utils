from typing import List, Optional, TYPE_CHECKING
from datetime import datetime
from pydantic import BaseModel, computed_field, Field, ConfigDict
from .order_item import OrderItemInput, OrderItemOut
from .client import ClientOut
import calendar

if TYPE_CHECKING:
    from .recurring_order import RecurringOrderOut

class OrderBase(BaseModel):
    client_id: Optional[int]

class OrderCreate(OrderBase):
    order_items: List[OrderItemInput]

class OrderUpdate(BaseModel):
    total: Optional[int] = None
    paid: Optional[bool] = None
    client_id: Optional[int] = None
    order_items: Optional[List[OrderItemInput]] = None

class OrderOut(OrderBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    total: int
    paid: bool
    recurring_order_id: Optional[int] = None
    generation_date: Optional[datetime] = None
    client_id: int
    client: Optional[ClientOut]
    company_id: int
    order_items: List[OrderItemOut]
    recurring_order: Optional["RecurringOrderOut"] = None

    @computed_field
    @property
    def generation_period(self) -> Optional[str]:
        """
        Compute a human-readable period label for recurring orders.
        Returns None if this is not a recurring order or if generation_date is not set.
        """
        if not self.generation_date or not self.recurring_order:
            return None

        recurrence = self.recurring_order.recurrence
        gen_date = self.generation_date

        if recurrence == "MONTHLY":
            return f"{calendar.month_name[gen_date.month]} {gen_date.year}"
        elif recurrence == "WEEKLY":
            week_num = gen_date.isocalendar()[1]
            return f"Week {week_num} {gen_date.year}"
        elif recurrence == "YEARLY":
            return f"{gen_date.year}"
        elif recurrence == "DAILY":
            return gen_date.strftime("%B %d, %Y")
        else:
            return gen_date.strftime("%B %d, %Y")
