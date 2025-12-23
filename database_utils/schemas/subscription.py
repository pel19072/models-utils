from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class SubscriptionOut(BaseModel):
    """Schema for returning subscription data"""
    id: int
    status: str
    billing_type: str
    current_period_start: datetime
    current_period_end: datetime
    cancel_at_period_end: bool
    canceled_at: Optional[datetime]
    trial_end: Optional[datetime]
    tier_id: int
    company_id: int
    stripe_subscription_id: Optional[str]

    class ConfigDict:
        from_attributes = True


class SubscriptionUpdate(BaseModel):
    """Schema for updating subscription"""
    tier_id: Optional[int] = None
    cancel_at_period_end: Optional[bool] = None


class SubscriptionWithTier(SubscriptionOut):
    """Schema for subscription with tier details"""
    tier_name: str
    tier_price: int
    tier_billing_cycle: str
