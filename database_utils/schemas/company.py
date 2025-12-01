# schemas/company.py
from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime


class CompanyBase(BaseModel):
    name: str
    email: Optional[EmailStr]
    phone: Optional[str] = None
    active: Optional[bool] = True
    start_date: Optional[datetime] = datetime.now()
    tier_id: Optional[int]
    tax_id: Optional[str]
    address: Optional[str] = ''


class CompanyCreate(CompanyBase):
    pass


class CompanyUpdate(BaseModel):
    """Used for PATCH - all fields optional"""
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    active: Optional[bool] = None
    start_date: Optional[datetime] = None
    tier_id: Optional[int] = None
    tax_id: Optional[str] = None
    address: Optional[str] = None


class CompanyOut(CompanyBase):
    id: int

    class ConfigDict:
        from_attributes = True
