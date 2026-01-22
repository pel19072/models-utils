# schemas/client.py
from pydantic import BaseModel, EmailStr
from typing import Optional
from uuid import UUID

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
    company_id: UUID  # required
    advisor_id: Optional[UUID] = None


class ClientUpdate(BaseModel):
    name: Optional[str]
    tax_id: Optional[str]
    address: Optional[str]
    phone: Optional[str]
    email: Optional[EmailStr]
    contact: Optional[str]
    observations: Optional[str]
    company_id: Optional[UUID]
    advisor_id: Optional[UUID]


class ClientOut(ClientBase):
    id: UUID
    company_id: UUID
    advisor_id: Optional[UUID]
    advisor: Optional[UserOut]

    class ConfigDict:
        from_attributes = True
