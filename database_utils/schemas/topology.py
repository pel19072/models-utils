# schemas/topology.py
"""
Topology (Cycle 2 D5 + Cycle 3 E1): a named ordered chain of device types with
purpose-keyed playbooks (topology_playbook, revision c3a_topology_purpose).
Replaces schemas/network.py (deleted in c2d_graph_removal — the free-form
graph is gone) and the single Topology.playbook_id/playbook shape (pre-c3a).

Resolution semantics live in database_utils/utils/provisioning_resolution.py
(moved in from backend-erp services/provisioning_resolution.py, Cycle 3 E2):
chain position -> device_type -> match against the client's assigned
inventory; purpose -> topology_playbook entry -> playbook. This module is
pure request/response shape.
"""
import re
from pydantic import BaseModel, ConfigDict, field_validator
from typing import Optional, List, Dict
from uuid import UUID
from datetime import datetime

from database_utils.models.isp import PURPOSE_ACTIVATION, TOPOLOGY_PURPOSE_PATTERN


def normalize_purpose(v: str) -> str:
    """strip -> upper -> regex-validate. Deliberately module-level and
    importable — the provision endpoint body schema (backend-erp
    ClientServiceProvisionIn, schemas/client_service.py) and the engine's
    ENQUEUE_PROVISIONING config path share this exact normalization so a
    tenant typing 'Activation' or 'activation ' always matches the seeded
    'ACTIVATION' row (doc 20a workflow-provisioning verifier fix on purpose
    string matching)."""
    p = v.strip().upper().replace(' ', '_').replace('-', '_')
    if not re.match(TOPOLOGY_PURPOSE_PATTERN, p):
        raise ValueError(f"purpose must match {TOPOLOGY_PURPOSE_PATTERN} (got '{v}')")
    return p


def _validate_playbooks_map(v: Dict[str, UUID]) -> Dict[str, UUID]:
    normalized: Dict[str, UUID] = {}
    for purpose, playbook_id in v.items():
        p = normalize_purpose(purpose)
        if p in normalized:
            raise ValueError(f"duplicate purpose after normalization: {p}")
        normalized[p] = playbook_id
    if PURPOSE_ACTIVATION not in normalized:
        raise ValueError('topology must define an ACTIVATION playbook')
    return normalized


class TopologyChainEntryOut(BaseModel):
    """One resolved position in a topology's device chain (read model)."""
    position: int
    device_type_id: UUID
    device_type_name: str
    # Cycle 3 E4: string device_category.key (model @property), not the old
    # devicecategory enum — no other change (appendix admin-categories §2).
    category: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class TopologyBase(BaseModel):
    name: str
    description: Optional[str] = None
    is_active: bool = True


class TopologyCreate(TopologyBase):
    # Ordered chain, position = list index. uq_topology_device_type (DB) backs
    # the "no duplicate type in one chain" rule the resolution algorithm
    # requires (D5: matching is BY TYPE, so a repeated type would be
    # ambiguous by construction).
    device_type_ids: List[UUID]
    # Cycle 3 E1: purpose -> playbook_id map, replacing the single
    # playbook_id field. ACTIVATION is a mandatory application invariant (not
    # DB-enforced — PG can't cheaply enforce "at least one child row"); it is
    # what makes the c3a downgrade total.
    playbooks: Dict[str, UUID]

    @field_validator("device_type_ids")
    @classmethod
    def validate_chain(cls, v: List[UUID]) -> List[UUID]:
        if not v:
            raise ValueError("topology must have at least one device type")
        if len(v) != len(set(v)):
            raise ValueError("device_type_ids must not contain duplicates")
        return v

    @field_validator("playbooks")
    @classmethod
    def validate_playbooks(cls, v: Dict[str, UUID]) -> Dict[str, UUID]:
        return _validate_playbooks_map(v)


class TopologyUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    # When present, replaces the WHOLE chain (bulk delete-orphan + recreate —
    # safe because nothing references topology_device_type rows by id).
    device_type_ids: Optional[List[UUID]] = None
    # When present, REPLACES the WHOLE purpose map (same semantics as
    # device_type_ids) and must still include ACTIVATION — an update can
    # never leave a topology without one.
    playbooks: Optional[Dict[str, UUID]] = None

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

    @field_validator("playbooks")
    @classmethod
    def validate_playbooks(cls, v: Optional[Dict[str, UUID]]) -> Optional[Dict[str, UUID]]:
        # Guard mirrors device_type_ids above: Pydantic field validators DO
        # run on an explicit `"playbooks": null` body (only skipped when the
        # key is omitted entirely) — without this guard, _validate_playbooks_map's
        # v.items() would 500 instead of cleanly no-op'ing the update.
        if v is None:
            return v
        return _validate_playbooks_map(v)


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
    # Cycle 3 E1: purpose -> playbook-lite map, replacing the single
    # playbook_id/playbook shape. Router populates via
    # {tp.purpose: tp.playbook for tp in topology.playbooks}.
    playbooks: Dict[str, _TopologyPlaybookOut] = {}
    chain: List[TopologyChainEntryOut] = []

    model_config = ConfigDict(from_attributes=True)
