# schemas/company.py
from pydantic import BaseModel, EmailStr, field_validator, ConfigDict
from typing import Optional
from datetime import datetime
from uuid import UUID
from database_utils.utils.timezone_utils import now_gt, make_aware_gt


class CompanyBase(BaseModel):
    name: str
    email: Optional[EmailStr]
    phone: Optional[str] = None
    active: Optional[bool] = True
    start_date: Optional[datetime] = None
    tier_id: Optional[UUID]
    tax_id: Optional[str]
    address: Optional[str] = ''

    @field_validator('start_date', mode='before')
    @classmethod
    def set_default_start_date(cls, v):
        """Set default start_date to current Guatemala time if not provided."""
        if v is None:
            return now_gt()
        # If provided, ensure it's timezone-aware
        if isinstance(v, datetime):
            return make_aware_gt(v)
        return v


class CompanyCreate(CompanyBase):
    pass


class CompanyUpdate(BaseModel):
    """Used for PATCH - all fields optional"""
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    active: Optional[bool] = None
    start_date: Optional[datetime] = None
    tier_id: Optional[UUID] = None
    tax_id: Optional[str] = None
    address: Optional[str] = None


class CompanyOut(CompanyBase):
    id: UUID

    model_config = ConfigDict(from_attributes=True)
