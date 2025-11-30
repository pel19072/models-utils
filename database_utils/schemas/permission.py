# schemas/permission.py
from pydantic import BaseModel
from typing import Optional


class PermissionBase(BaseModel):
    name: str
    resource: str
    action: str
    description: Optional[str] = None


class PermissionCreate(PermissionBase):
    pass


class PermissionUpdate(BaseModel):
    """Used for PATCH - all fields optional"""
    name: Optional[str] = None
    resource: Optional[str] = None
    action: Optional[str] = None
    description: Optional[str] = None


class PermissionOut(PermissionBase):
    id: int

    class ConfigDict:
        from_attributes = True
