# schemas/topology.py
"""
Topology (Cycle 2 D5): a named ordered chain of device types bound to the
playbook that provisions it. Replaces schemas/network.py (deleted in the same
commit as revision c2d_graph_removal — the free-form graph is gone).

Resolution semantics live in backend-erp services/provisioning_resolution.py:
chain position -> device_type -> match against the client's assigned
inventory. This module is pure request/response shape.
"""
from pydantic import BaseModel, ConfigDict, field_validator
from typing import Optional, List
from uuid import UUID
from datetime import datetime

from database_utils.models.isp import DeviceCategory


class TopologyChainEntryOut(BaseModel):
    """One resolved position in a topology's device chain (read model)."""
    position: int
    device_type_id: UUID
    device_type_name: str
    category: Optional[DeviceCategory] = None

    model_config = ConfigDict(from_attributes=True)


class TopologyBase(BaseModel):
    name: str
    description: Optional[str] = None
    playbook_id: UUID
    is_active: bool = True


class TopologyCreate(TopologyBase):
    # Ordered chain, position = list index. uq_topology_device_type (DB) backs
    # the "no duplicate type in one chain" rule the resolution algorithm
    # requires (D5: matching is BY TYPE, so a repeated type would be
    # ambiguous by construction).
    device_type_ids: List[UUID]

    @field_validator("device_type_ids")
    @classmethod
    def validate_chain(cls, v: List[UUID]) -> List[UUID]:
        if not v:
            raise ValueError("topology must have at least one device type")
        if len(v) != len(set(v)):
            raise ValueError("device_type_ids must not contain duplicates")
        return v


class TopologyUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    playbook_id: Optional[UUID] = None
    is_active: Optional[bool] = None
    # When present, replaces the WHOLE chain (bulk delete-orphan + recreate —
    # safe because nothing references topology_device_type rows by id).
    device_type_ids: Optional[List[UUID]] = None

    @field_validator("device_type_ids")
    @classmethod
    def validate_chain(cls, v: Optional[List[UUID]]) -> Optional[List[UUID]]:
        if v is None:
            return v
        if not v:
            raise ValueError("topology must have at least one device type")
        if len(v) != len(set(v)):
            raise ValueError("device_type_ids must not contain duplicates")
        return v


class _TopologyPlaybookOut(BaseModel):
    """Playbook-lite for embedding in TopologyOut (avoids importing the full
    PlaybookOut, which requires the definition JSON validated shape)."""
    id: UUID
    name: str
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class TopologyOut(TopologyBase):
    id: UUID
    company_id: UUID
    created_at: datetime
    updated_at: datetime
    playbook: Optional[_TopologyPlaybookOut] = None
    chain: List[TopologyChainEntryOut] = []

    model_config = ConfigDict(from_attributes=True)
