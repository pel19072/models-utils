# schemas/network.py
from pydantic import BaseModel, ConfigDict, field_validator
from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime

from database_utils.models.isp import DeviceCategory, NetworkNodeStatus
from .inventory import AttributeDefinition


# --- NetworkNodeType (config-driven node kinds, ADR-003) ---

class NetworkNodeTypeBase(BaseModel):
    key: str
    name: str
    category: Optional[DeviceCategory] = None
    icon: Optional[str] = None
    allowed_parent_keys: Optional[List[str]] = None
    attribute_schema: Optional[List[AttributeDefinition]] = None

    @field_validator("key")
    @classmethod
    def validate_key(cls, v: str) -> str:
        import re
        if not re.fullmatch(r"[a-z][a-z0-9_]*", v):
            raise ValueError("key must be snake_case (lowercase letters, digits, underscores)")
        return v


class NetworkNodeTypeCreate(NetworkNodeTypeBase):
    pass


class NetworkNodeTypeUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[DeviceCategory] = None
    icon: Optional[str] = None
    allowed_parent_keys: Optional[List[str]] = None
    attribute_schema: Optional[List[AttributeDefinition]] = None


class NetworkNodeTypeOut(NetworkNodeTypeBase):
    id: UUID
    company_id: UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# --- NetworkNode ---

class NetworkNodeBase(BaseModel):
    name: str
    node_type_id: UUID
    parent_id: Optional[UUID] = None
    status: NetworkNodeStatus = NetworkNodeStatus.ACTIVE
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    capacity: Optional[int] = None
    attributes: Optional[Dict[str, Any]] = None
    inventory_item_id: Optional[UUID] = None
    notes: Optional[str] = None


class NetworkNodeCreate(NetworkNodeBase):
    pass


class NetworkNodeUpdate(BaseModel):
    name: Optional[str] = None
    node_type_id: Optional[UUID] = None
    parent_id: Optional[UUID] = None
    status: Optional[NetworkNodeStatus] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    capacity: Optional[int] = None
    attributes: Optional[Dict[str, Any]] = None
    inventory_item_id: Optional[UUID] = None
    notes: Optional[str] = None


class NetworkNodeOut(NetworkNodeBase):
    id: UUID
    company_id: UUID
    created_at: datetime
    node_type: Optional[NetworkNodeTypeOut] = None

    model_config = ConfigDict(from_attributes=True)


class NetworkNodeTreeOut(NetworkNodeOut):
    """Node with recursively nested children (topology tree endpoint)."""
    children: List["NetworkNodeTreeOut"] = []


NetworkNodeTreeOut.model_rebuild()


# --- NetworkLink ---

class NetworkLinkBase(BaseModel):
    from_node_id: UUID
    to_node_id: UUID
    link_type: str = "fiber"
    attributes: Optional[Dict[str, Any]] = None


class NetworkLinkCreate(NetworkLinkBase):
    pass


class NetworkLinkOut(NetworkLinkBase):
    id: UUID
    company_id: UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
