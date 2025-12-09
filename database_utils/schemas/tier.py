# schemas/company.py
from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class TierBase(BaseModel):
    name: str
    created_at: Optional[datetime] = datetime.now()


class TierCreate(TierBase):
    pass


class TierUpdate(BaseModel):
    """Used for PATCH - all fields optional"""
    name: Optional[str] = None
    created_at: Optional[datetime] = None


class TierOut(TierBase):
    id: int

    class ConfigDict:
        from_attributes = True
