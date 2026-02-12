from pydantic import BaseModel, EmailStr, ConfigDict
from typing import Optional, List
from datetime import datetime
from uuid import UUID


class InvitationCreate(BaseModel):
    """Schema for creating a user invitation"""
    email: EmailStr
    name: Optional[str] = None
    role_ids: List[UUID] = []


class InvitationOut(BaseModel):
    """Schema for returning invitation data"""
    id: UUID
    created_at: datetime
    expires_at: datetime
    email: str
    name: Optional[str]
    status: str
    company_id: UUID
    invited_by_user_id: Optional[UUID]

    model_config = ConfigDict(from_attributes=True)


class InvitationAccept(BaseModel):
    """Schema for accepting an invitation"""
    token: str
    name: str
    age: int
    password: str


class InvitationValidate(BaseModel):
    """Schema for validating an invitation token"""
    token: str
    valid: bool
    email: Optional[str] = None
    company_name: Optional[str] = None
    expires_at: Optional[datetime] = None
    message: Optional[str] = None
