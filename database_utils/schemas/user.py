# schemas/user.py
from pydantic import BaseModel, EmailStr, constr
from typing import Optional, List


class UserBase(BaseModel):
    name: str
    email: EmailStr
    age: int
    role: Optional[str] = "USER"
    admin: Optional[bool] = False


class UserCreate(UserBase):
    password: constr(min_length=6)
    company_id: Optional[int] = 0
    role_ids: Optional[List[int]] = []


class UserUpdate(BaseModel):
    name: Optional[str]
    email: Optional[EmailStr]
    age: Optional[int]
    role: Optional[str]
    admin: Optional[bool]
    password: Optional[constr(min_length=6)]
    company_id: Optional[int]
    role_ids: Optional[List[int]] = None


class UserOut(UserBase):
    id: int
    company_id: int

    class ConfigDict:
        from_attributes = True


class UserWithRoles(UserOut):
    """Extended user model with role details"""
    roles: List = []

    class ConfigDict:
        from_attributes = True
