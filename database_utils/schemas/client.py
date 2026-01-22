# schemas/client.py
from pydantic import BaseModel, EmailStr
from typing import Optional, List
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
    custom_field_values: Optional[List["ClientCustomFieldValueInput"]] = None


class ClientUpdate(BaseModel):
    name: Optional[str] = None
    tax_id: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    contact: Optional[str] = None
    observations: Optional[str] = None
    company_id: Optional[UUID] = None
    advisor_id: Optional[UUID] = None
    custom_field_values: Optional[List["ClientCustomFieldValueInput"]] = None


class ClientOut(ClientBase):
    id: UUID
    company_id: UUID
    advisor_id: Optional[UUID]
    advisor: Optional[UserOut] = None
    custom_field_values: Optional[List["ClientCustomFieldValueOut"]] = None

    class ConfigDict:
        from_attributes = True


# Import at the end to avoid circular imports
from .custom_field import ClientCustomFieldValueInput, ClientCustomFieldValueOut

# Rebuild model to resolve forward references
ClientCreate.model_rebuild()
ClientUpdate.model_rebuild()
ClientOut.model_rebuild()
