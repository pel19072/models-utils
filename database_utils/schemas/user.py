# schemas/user.py
from pydantic import BaseModel, EmailStr, constr
from typing import Optional


class UserBase(BaseModel):
    name: str
    email: EmailStr
    age: int
    role: Optional[str] = "USER"
    admin: Optional[bool] = False


class UserCreate(UserBase):
    password: constr(min_length=6)
    company_id: int


class UserUpdate(BaseModel):
    name: Optional[str]
    email: Optional[EmailStr]
    age: Optional[int]
    role: Optional[str]
    admin: Optional[bool]
    password: Optional[constr(min_length=6)]
    company_id: Optional[int]


class UserOut(UserBase):
    id: int
    company_id: int

    class Config:
        orm_mode = True
