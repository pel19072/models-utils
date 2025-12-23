from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime


class InvitationCreate(BaseModel):
    """Schema for creating a user invitation"""
    email: EmailStr
    name: Optional[str] = None
    role_ids: List[int] = []


class InvitationOut(BaseModel):
    """Schema for returning invitation data"""
    id: int
    created_at: datetime
    expires_at: datetime
    email: str
    name: Optional[str]
    status: str
    company_id: int
    invited_by_user_id: Optional[int]

    class ConfigDict:
        from_attributes = True


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
