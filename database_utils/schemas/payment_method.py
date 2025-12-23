from pydantic import BaseModel
from typing import Optional


class PaymentMethodCreate(BaseModel):
    """Schema for creating a payment method (mock)"""
    card_number: str  # Mock: will store only last 4
    expiry_month: int
    expiry_year: int
    brand: str  # "visa", "mastercard", "amex"


class PaymentMethodOut(BaseModel):
    """Schema for returning payment method data"""
    id: int
    type: str
    last4: str
    expiry_month: Optional[int]
    expiry_year: Optional[int]
    brand: Optional[str]
    is_default: bool
    is_active: bool

    class ConfigDict:
        from_attributes = True


class PaymentMethodSetDefault(BaseModel):
    """Schema for setting default payment method"""
    is_default: bool = True
