# schemas/playbook.py
"""
Declarative playbook format (ADR-005/006).

A playbook definition is uploadable JSON (or YAML converted client-side):

{
  "variables": [
    {"key": "onu_serial", "label": "ONU Serial", "type": "TEXT", "required": true},
    {"key": "vlan", "label": "Service VLAN", "type": "NUMBER", "required": true}
  ],
  "steps": [
    {
      "name": "register-onu",
      "driver": "simulator",           // simulator | http | ssh | telnet | snmp | tr069
      "template": "interface gpon 0/1\\n ont add {{onu_serial}} vlan {{vlan}}",
      "request": null,                  // http driver: {"method","path","headers","body"}
      "validation": {"expect_contains": "success", "expect_status": 200},
      "timeout_seconds": 30
    }
  ],
  "rollback": [ ...same step shape... ]
}

Templates use {{variable}} substitution only — no expressions, no code execution.
"""
from pydantic import BaseModel, ConfigDict, field_validator, model_validator
from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime

from database_utils.models.isp import (
    DeviceCategory,
    ProvisioningJobStatus,
    ProvisioningTrigger,
)

PLAYBOOK_DRIVERS = {"simulator", "http", "ssh", "telnet", "snmp", "tr069"}
_VAR_TYPES = {"TEXT", "NUMBER", "BOOLEAN"}


class PlaybookVariable(BaseModel):
    key: str
    label: Optional[str] = None
    type: str = "TEXT"
    required: bool = False
    default: Optional[Any] = None

    @field_validator("key")
    @classmethod
    def validate_key(cls, v: str) -> str:
        import re
        if not re.fullmatch(r"[a-z][a-z0-9_]*", v):
            raise ValueError("variable key must be snake_case")
        return v

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        if v not in _VAR_TYPES:
            raise ValueError(f"variable type must be one of {sorted(_VAR_TYPES)}")
        return v


class PlaybookStepValidation(BaseModel):
    expect_contains: Optional[str] = None
    expect_not_contains: Optional[str] = None
    expect_status: Optional[int] = None  # http driver


class PlaybookStep(BaseModel):
    name: str
    driver: str
    template: Optional[str] = None            # command-style drivers
    request: Optional[Dict[str, Any]] = None  # http driver
    validation: Optional[PlaybookStepValidation] = None
    timeout_seconds: int = 30

    @field_validator("driver")
    @classmethod
    def validate_driver(cls, v: str) -> str:
        if v not in PLAYBOOK_DRIVERS:
            raise ValueError(f"driver must be one of {sorted(PLAYBOOK_DRIVERS)}")
        return v

    @model_validator(mode="after")
    def validate_payload(self) -> "PlaybookStep":
        if self.driver == "http":
            if not self.request:
                raise ValueError(f"step '{self.name}': http driver requires 'request'")
        elif not self.template:
            raise ValueError(f"step '{self.name}': driver '{self.driver}' requires 'template'")
        if not (1 <= self.timeout_seconds <= 600):
            raise ValueError(f"step '{self.name}': timeout_seconds must be 1-600")
        return self


class PlaybookDefinition(BaseModel):
    variables: List[PlaybookVariable] = []
    steps: List[PlaybookStep]
    rollback: List[PlaybookStep] = []

    @model_validator(mode="after")
    def validate_definition(self) -> "PlaybookDefinition":
        if not self.steps:
            raise ValueError("playbook must have at least one step")
        names = [s.name for s in self.steps]
        if len(names) != len(set(names)):
            raise ValueError("step names must be unique")
        return self


class PlaybookBase(BaseModel):
    name: str
    description: Optional[str] = None
    target_vendor: Optional[str] = None
    target_category: Optional[DeviceCategory] = None
    is_active: bool = True
    definition: PlaybookDefinition


class PlaybookCreate(PlaybookBase):
    pass


class PlaybookUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    target_vendor: Optional[str] = None
    target_category: Optional[DeviceCategory] = None
    is_active: Optional[bool] = None
    definition: Optional[PlaybookDefinition] = None


class PlaybookOut(PlaybookBase):
    id: UUID
    company_id: UUID
    version: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# --- ProvisioningJob ---

class ProvisioningJobCreate(BaseModel):
    playbook_id: UUID
    variables: Optional[Dict[str, Any]] = None
    client_service_id: Optional[UUID] = None
    network_node_id: Optional[UUID] = None
    inventory_item_id: Optional[UUID] = None
    integration_id: Optional[UUID] = None
    idempotency_key: Optional[str] = None
    max_attempts: int = 3
    scheduled_for: Optional[datetime] = None


class ProvisioningJobOut(BaseModel):
    id: UUID
    company_id: UUID
    playbook_id: UUID
    status: ProvisioningJobStatus
    attempts: int
    max_attempts: int
    idempotency_key: Optional[str] = None
    scheduled_for: Optional[datetime] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    variables: Optional[Dict[str, Any]] = None
    log: Optional[Any] = None
    error: Optional[str] = None
    triggered_by: ProvisioningTrigger
    triggered_by_user_id: Optional[UUID] = None
    client_service_id: Optional[UUID] = None
    network_node_id: Optional[UUID] = None
    inventory_item_id: Optional[UUID] = None
    integration_id: Optional[UUID] = None
    created_at: datetime
    playbook: Optional[PlaybookOut] = None

    model_config = ConfigDict(from_attributes=True)
