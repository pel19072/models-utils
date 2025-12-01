# schemas/permission.py
from pydantic import BaseModel, field_validator
from typing import Optional


class PermissionBase(BaseModel):
    name: str
    resource: str
    action: str
    description: Optional[str] = None

    @field_validator('name')
    @classmethod
    def validate_name_format(cls, v):
        if '.' not in v:
            raise ValueError('Permission name must follow pattern: resource.action')
        parts = v.split('.')
        if len(parts) != 2:
            raise ValueError('Permission name must have exactly one dot separator')
        return v


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
