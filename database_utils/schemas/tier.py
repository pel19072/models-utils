# schemas/tier.py
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from uuid import UUID


class TierBase(BaseModel):
    name: str
    price: int = 0  # Price in cents
    billing_cycle: str = "MONTHLY"  # MONTHLY, YEARLY
    features: Optional[dict] = None
    is_active: bool = True


class TierCreate(TierBase):
    pass


class TierUpdate(BaseModel):
    """Used for PATCH - all fields optional"""
    name: Optional[str] = None
    price: Optional[int] = None
    billing_cycle: Optional[str] = None
    features: Optional[dict] = None
    is_active: Optional[bool] = None


class TierOut(TierBase):
    id: UUID
    created_at: datetime
    stripe_price_id: Optional[str] = None

    class ConfigDict:
        from_attributes = True
