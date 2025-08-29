# schemas/client.py
from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime

from .user import UserOut


class ClientBase(BaseModel):
    name: str
    tax_id: Optional[str]
    address: Optional[str]
    phone: Optional[str]
    email: Optional[EmailStr]
    contact: Optional[str]
    observations: Optional[str]


class ClientCreate(ClientBase):
    company_id: int  # required
    advisor_id: Optional[int] = None


class ClientUpdate(BaseModel):
    name: Optional[str]
    tax_id: Optional[str]
    address: Optional[str]
    phone: Optional[str]
    email: Optional[EmailStr]
    contact: Optional[str]
    observations: Optional[str]
    company_id: Optional[int]
    advisor_id: Optional[int]


class ClientOut(ClientBase):
    id: int
    company_id: int
    advisor_id: Optional[int]
    advisor: Optional[UserOut]

    class ConfigDict:
        from_attributes = True
