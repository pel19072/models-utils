# schemas/user.py
from pydantic import BaseModel, EmailStr, constr
from typing import Optional, List
from uuid import UUID


class UserBase(BaseModel):
    """Base user schema without legacy role/admin fields"""
    name: str
    email: EmailStr
    age: int


class UserCreate(UserBase):
    """Schema for creating a new user with role assignments"""
    password: constr(min_length=6)
    company_id: Optional[UUID] = None
    role_ids: Optional[List[UUID]] = []


class UserUpdate(BaseModel):
    """Schema for updating user information"""
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    age: Optional[int] = None
    password: Optional[constr(min_length=6)] = None
    company_id: Optional[UUID] = None
    role_ids: Optional[List[UUID]] = None


class UserOut(UserBase):
    """Output schema for user information"""
    id: UUID
    company_id: Optional[UUID] = None
    is_super_admin: Optional[bool] = False

    class ConfigDict:
        from_attributes = True


class UserWithRoles(UserOut):
    """Extended user model with role details"""
    roles: List = []

    class ConfigDict:
        from_attributes = True


class SuperAdminCreate(BaseModel):
    """Schema for creating a super admin user (no company_id required)"""
    name: str
    email: EmailStr
    age: int
    password: constr(min_length=6)
    is_super_admin: Optional[bool] = True
