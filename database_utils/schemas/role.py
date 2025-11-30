# schemas/role.py
from pydantic import BaseModel
from typing import Optional, List
from .permission import PermissionOut


class RoleBase(BaseModel):
    name: str
    description: Optional[str] = None
    is_system: Optional[bool] = False


class RoleCreate(RoleBase):
    permission_ids: Optional[List[int]] = []


class RoleUpdate(BaseModel):
    """Used for PATCH - all fields optional"""
    name: Optional[str] = None
    description: Optional[str] = None
    permission_ids: Optional[List[int]] = None


class RoleOut(RoleBase):
    id: int
    permissions: List[PermissionOut] = []

    class ConfigDict:
        from_attributes = True


class RoleWithPermissions(RoleOut):
    """Extended role model with full permission details"""
    pass
