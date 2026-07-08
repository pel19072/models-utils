# schemas/client_service.py
"""
Cycle 2 D1 (entity merge): ClientService absorbs RecurringOrder billing.
`migration_source` is a dedicated marker column (doc 18 amendment 1) and is
NEVER exposed on any Create/Update/Out schema that accepts client input —
Out below intentionally omits it (it is an internal/audit-only column,
readable only via direct DB inspection or a future admin-only export).
`recurring_order_id` is dropped from ClientServiceUpdate: it is
migration-critical bridge state, not user-editable data (amendment 1).
"""
from pydantic import BaseModel, ConfigDict, field_validator
from typing import Optional, Dict, Any
from uuid import UUID
from datetime import datetime

from database_utils.models.isp import ClientServiceStatus, PURPOSE_ACTIVATION, SuspensionReason
from database_utils.models.crm import RecurrenceEnum, RecurringOrderStatus
from .service_plan import ServicePlanOut
from .topology import normalize_purpose


class ClientServiceBase(BaseModel):
    client_id: UUID
    service_plan_id: UUID
    # D5: replaces network_node_id (removed in revision c2d_graph_removal).
    # Nullable — legacy/non-provisioned services may have none.
    topology_id: Optional[UUID] = None
    connection_params: Optional[Dict[str, Any]] = None
    notes: Optional[str] = None


class ClientServiceCreate(ClientServiceBase):
    # --- Billing (Cycle 2 D1 §2a): the backend sets billing_status/
    # next_generation_date directly on create — no shadow recurring_order row
    # is written anymore for post-merge services. ---
    recurrence: RecurrenceEnum = RecurrenceEnum.MONTHLY
    recurrence_end: Optional[datetime] = None
    enable_billing: bool = True
    bill_immediately: bool = True
    quantity: int = 1
    # Deprecated alias for enable_billing, kept so callers built against the
    # pre-merge contract don't 422 during the rollback window (doc 18 §2a).
    create_recurring_order: Optional[bool] = None


class ClientServiceUpdate(BaseModel):
    status: Optional[ClientServiceStatus] = None
    service_plan_id: Optional[UUID] = None
    topology_id: Optional[UUID] = None
    activation_date: Optional[datetime] = None
    connection_params: Optional[Dict[str, Any]] = None
    notes: Optional[str] = None


class ClientServiceBillingUpdate(BaseModel):
    """Dedicated billing update flow (doc 18 §2a) — deliberately separate from
    ClientServiceUpdate so a generic PATCH can never accidentally touch
    billing state. Ports the pre-merge PATCH semantics verbatim: transitioning
    billing_status to PAUSED clears next_generation_date; PAUSED->ACTIVE with
    a NULL date sets it to now (no overdue backlog)."""
    billing_status: Optional[RecurringOrderStatus] = None
    recurrence: Optional[RecurrenceEnum] = None
    recurrence_end: Optional[datetime] = None
    next_generation_date: Optional[datetime] = None
    quantity: Optional[int] = None


class ClientServiceOut(ClientServiceBase):
    id: UUID
    company_id: UUID
    status: ClientServiceStatus
    activation_date: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    created_at: datetime
    service_plan: Optional[ServicePlanOut] = None
    # Cycle 5 Phase 1 (functionality F1.4/F2.3): learned network identifiers
    # written by the provisioning executor at settlement, read back by
    # suspension/reactivation/deprovision playbooks. Read-only here.
    provisioning_state: Optional[Dict[str, Any]] = None

    # --- Billing (read-only here; settable via ClientServiceCreate or the
    # dedicated ClientServiceBillingUpdate / generate / regenerate-charges
    # flows — never via the general ClientServiceUpdate PATCH). ---
    recurrence: Optional[RecurrenceEnum] = None
    recurrence_end: Optional[datetime] = None
    next_generation_date: Optional[datetime] = None
    last_generated_at: Optional[datetime] = None
    billing_status: Optional[RecurringOrderStatus] = None
    quantity: int = 1
    # Read-only audit/bridge visibility (never accepted on Update — amendment
    # 1 removes it from the PATCHable field set, but it is legitimate
    # read-only signal for understanding a migrated service's billing bridge).
    recurring_order_id: Optional[UUID] = None

    model_config = ConfigDict(from_attributes=True)


class ClientServiceProvisionIn(BaseModel):
    """Cycle 3 E1 (doc 20a D-E1.3): POST /client-services/{id}/provision body.
    Optional — no body (or omitting purpose) defaults to ACTIVATION, so
    pre-Cycle-3 callers are unaffected. `purpose` selects the topology's
    purpose-map entry (see database_utils.utils.provisioning_resolution)."""
    purpose: str = PURPOSE_ACTIVATION

    @field_validator('purpose')
    @classmethod
    def _normalize(cls, v: str) -> str:
        return normalize_purpose(v)


class ServiceSuspensionCreate(BaseModel):
    reason: SuspensionReason = SuspensionReason.OTHER
    note: Optional[str] = None


class ServiceSuspensionOut(BaseModel):
    id: UUID
    company_id: UUID
    client_service_id: UUID
    suspended_at: datetime
    reactivated_at: Optional[datetime] = None
    reason: SuspensionReason
    note: Optional[str] = None
    created_by: Optional[UUID] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
