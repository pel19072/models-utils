from pydantic import BaseModel, ConfigDict
from typing import Optional, Dict, Any
from uuid import UUID
from datetime import datetime

from database_utils.models.crm import IntegrationAuthType

MASKED = "***"
SENSITIVE_KEYS = {"api_key", "token", "password"}


class IntegrationCreate(BaseModel):
    name: str
    description: Optional[str] = None
    base_url: str
    auth_type: IntegrationAuthType = IntegrationAuthType.NONE
    credentials: Optional[Dict[str, Any]] = None


class IntegrationUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    base_url: Optional[str] = None
    auth_type: Optional[IntegrationAuthType] = None
    credentials: Optional[Dict[str, Any]] = None


class IntegrationOut(BaseModel):
    id: UUID
    company_id: UUID
    name: str
    description: Optional[str] = None
    base_url: str
    auth_type: IntegrationAuthType
    credentials: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_orm_masked(cls, obj) -> "IntegrationOut":
        """Return an IntegrationOut with sensitive credential values replaced by ***."""
        instance = cls.model_validate(obj)
        if instance.credentials:
            instance.credentials = {
                k: MASKED if k in SENSITIVE_KEYS else v
                for k, v in instance.credentials.items()
            }
        return instance
