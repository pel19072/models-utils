# schemas/network_access.py
"""
Network access (Cycle 5 Phase 1, canon C9): per-tenant transport configuration,
multiple rows per tenant keyed by `kind` (acs|olt). Plan:
docs/isp-platform/23-network-config-implementation-plan.md §2.2.

CIDR validation (valid networks) lives here in the schema, not the DB — same
tier as the topology-purpose normalizer. Standard multi-record CRUD (no
singleton PUT).
"""
import ipaddress
from pydantic import BaseModel, ConfigDict, field_validator
from typing import Optional, List
from uuid import UUID
from datetime import datetime

from database_utils.models.isp import NETWORK_ACCESS_KINDS, NETWORK_ACCESS_MODES


def _validate_subnets(v: Optional[List[str]]) -> Optional[List[str]]:
    if v is None:
        return v
    for cidr in v:
        try:
            ipaddress.ip_network(cidr, strict=False)
        except ValueError as exc:
            raise ValueError(f"invalid CIDR '{cidr}': {exc}") from exc
    return v


class NetworkAccessBase(BaseModel):
    name: str
    kind: str
    mode: str = "direct"
    is_default: bool = False
    mgmt_subnets: Optional[List[str]] = None
    acs_base_url: Optional[str] = None

    @field_validator("kind")
    @classmethod
    def validate_kind(cls, v: str) -> str:
        if v not in NETWORK_ACCESS_KINDS:
            raise ValueError(f"kind must be one of {sorted(NETWORK_ACCESS_KINDS)}")
        return v

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, v: str) -> str:
        if v not in NETWORK_ACCESS_MODES:
            raise ValueError(f"mode must be one of {sorted(NETWORK_ACCESS_MODES)}")
        return v

    @field_validator("mgmt_subnets")
    @classmethod
    def validate_subnets(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        return _validate_subnets(v)


class NetworkAccessCreate(NetworkAccessBase):
    pass


class NetworkAccessUpdate(BaseModel):
    name: Optional[str] = None
    kind: Optional[str] = None
    mode: Optional[str] = None
    is_default: Optional[bool] = None
    mgmt_subnets: Optional[List[str]] = None
    acs_base_url: Optional[str] = None

    @field_validator("kind")
    @classmethod
    def validate_kind(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if v not in NETWORK_ACCESS_KINDS:
            raise ValueError(f"kind must be one of {sorted(NETWORK_ACCESS_KINDS)}")
        return v

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if v not in NETWORK_ACCESS_MODES:
            raise ValueError(f"mode must be one of {sorted(NETWORK_ACCESS_MODES)}")
        return v

    @field_validator("mgmt_subnets")
    @classmethod
    def validate_subnets(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        return _validate_subnets(v)


class NetworkAccessOut(NetworkAccessBase):
    id: UUID
    company_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
