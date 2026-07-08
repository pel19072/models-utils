# schemas/inventory.py
from pydantic import BaseModel, ConfigDict, field_validator
from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime

from database_utils.models.isp import (
    InventoryItemStatus,
    InventoryItemCondition,
    EquipmentEventType,
)


# --- Attribute schema entries (device_type.attribute_schema) ---

_ALLOWED_ATTR_TYPES = {"TEXT", "NUMBER", "BOOLEAN", "DATE", "ENUM"}


class AttributeDefinition(BaseModel):
    key: str
    label: str
    type: str = "TEXT"
    required: bool = False
    options: Optional[List[str]] = None  # for ENUM
    unit: Optional[str] = None

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        if v not in _ALLOWED_ATTR_TYPES:
            raise ValueError(f"type must be one of {sorted(_ALLOWED_ATTR_TYPES)}")
        return v

    @field_validator("key")
    @classmethod
    def validate_key(cls, v: str) -> str:
        import re
        if not re.fullmatch(r"[a-z][a-z0-9_]*", v):
            raise ValueError("key must be snake_case (lowercase letters, digits, underscores)")
        return v


# --- DeviceType ---

class DeviceTypeBase(BaseModel):
    name: str
    # Cycle 3 E4: device_category.key (a plain string, server-resolved and
    # validated against the device_category table) — replaces the
    # `devicecategory` PG enum (dropped in revision c3b_device_categories).
    # Unknown keys previously 422'd via FastAPI enum coercion; the router
    # must now resolve the key -> id explicitly and 422 on unknown/inactive.
    category: str = 'OTHER'
    vendor: Optional[str] = None
    model: Optional[str] = None
    description: Optional[str] = None
    attribute_schema: Optional[List[AttributeDefinition]] = None
    default_attributes: Optional[Dict[str, Any]] = None
    # Cycle 5 Phase 1 (canon C6): device-group provisioning opt-out gate.
    provisioning_enabled: bool = True


class DeviceTypeCreate(DeviceTypeBase):
    pass


class DeviceTypeUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    vendor: Optional[str] = None
    model: Optional[str] = None
    description: Optional[str] = None
    attribute_schema: Optional[List[AttributeDefinition]] = None
    default_attributes: Optional[Dict[str, Any]] = None
    provisioning_enabled: Optional[bool] = None


class DeviceTypeOut(DeviceTypeBase):
    id: UUID
    company_id: UUID
    # Cycle 3 E4: the resolved FK id, alongside the string `category` key
    # (inherited from DeviceTypeBase, populated from the model's @property).
    category_id: UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# --- Warehouse ---

class WarehouseBase(BaseModel):
    name: str
    address: Optional[str] = None
    is_vehicle: bool = False
    notes: Optional[str] = None


class WarehouseCreate(WarehouseBase):
    pass


class WarehouseUpdate(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
    is_vehicle: Optional[bool] = None
    notes: Optional[str] = None


class WarehouseOut(WarehouseBase):
    id: UUID
    company_id: UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# --- InventoryItem ---

class InventoryItemBase(BaseModel):
    device_type_id: UUID
    serial_number: Optional[str] = None
    mac_address: Optional[str] = None
    # Cycle 5 Phase 1 (canon C13): device-identity half paired with serial for
    # the acs_device_registration match.
    oui: Optional[str] = None
    condition: InventoryItemCondition = InventoryItemCondition.NEW
    warehouse_id: Optional[UUID] = None
    attributes: Optional[Dict[str, Any]] = None
    purchase_date: Optional[datetime] = None
    warranty_until: Optional[datetime] = None
    cost: Optional[float] = None
    notes: Optional[str] = None


class InventoryItemCreate(InventoryItemBase):
    pass


class InventoryItemUpdate(BaseModel):
    serial_number: Optional[str] = None
    mac_address: Optional[str] = None
    oui: Optional[str] = None
    status: Optional[InventoryItemStatus] = None
    condition: Optional[InventoryItemCondition] = None
    warehouse_id: Optional[UUID] = None
    client_id: Optional[UUID] = None
    client_service_id: Optional[UUID] = None
    attributes: Optional[Dict[str, Any]] = None
    purchase_date: Optional[datetime] = None
    warranty_until: Optional[datetime] = None
    cost: Optional[float] = None
    notes: Optional[str] = None


class InventoryItemOut(InventoryItemBase):
    id: UUID
    company_id: UUID
    status: InventoryItemStatus
    client_id: Optional[UUID] = None
    client_service_id: Optional[UUID] = None
    created_at: datetime
    device_type: Optional[DeviceTypeOut] = None
    warehouse: Optional[WarehouseOut] = None

    model_config = ConfigDict(from_attributes=True)


# --- EquipmentEvent ---

class EquipmentEventCreate(BaseModel):
    event_type: EquipmentEventType
    notes: Optional[str] = None
    event_metadata: Optional[Dict[str, Any]] = None
    related_item_id: Optional[UUID] = None
    from_warehouse_id: Optional[UUID] = None
    to_warehouse_id: Optional[UUID] = None
    client_id: Optional[UUID] = None
    client_service_id: Optional[UUID] = None
    technician_id: Optional[UUID] = None


class EquipmentEventOut(EquipmentEventCreate):
    id: UUID
    company_id: UUID
    item_id: UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
