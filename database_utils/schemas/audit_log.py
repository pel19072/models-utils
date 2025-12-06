# schemas/audit_log.py
from pydantic import BaseModel
from typing import Optional, Any
from datetime import datetime


class AuditLogBase(BaseModel):
    """Base schema for AuditLog"""
    action: str
    resource_type: str
    resource_id: Optional[int] = None
    details: Optional[dict[str, Any]] = None
    ip_address: Optional[str] = None


class AuditLogCreate(AuditLogBase):
    """Schema for creating an audit log entry"""
    user_id: Optional[int] = None


class AuditLogOut(AuditLogBase):
    """Schema for audit log output"""
    id: int
    created_at: datetime
    user_id: Optional[int] = None

    class ConfigDict:
        from_attributes = True
