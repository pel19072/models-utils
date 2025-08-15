# schemas/company.py
from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime


class TierBase(BaseModel):
    name: str
    email: Optional[EmailStr]
    active: Optional[bool] = True
    start_date: Optional[datetime] = datetime.now()
    plan_id: Optional[str]
    tax_id: Optional[str]
    address: Optional[str] = ''


class TierCreate(TierBase):
    pass


class TierUpdate(BaseModel):
    """Used for PATCH - all fields optional"""
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    active: Optional[bool] = None
    start_date: Optional[datetime] = None
    plan_id: Optional[str] = None
    tax_id: Optional[str] = None
    address: Optional[str] = None


class TierOut(TierBase):
    id: int

    class Config:
        orm_mode = True
