# schemas/client_service.py
"""
Cycle 2 D1 (entity merge): ClientService absorbs RecurringOrder billing.
`migration_source` is a dedicated marker column (doc 18 amendment 1) and is
NEVER exposed on any Create/Update/Out schema that accepts client input —
Out below intentionally omits it (it is an internal/audit-only column,
readable only via direct DB inspection or a future admin-only export).
`recurring_order_id` is dropped from ClientServiceUpdate: it is
migration-critical bridge state, not user-editable data (amendment 1).
The ba1 adopted_* fields follow the same rule: Out-only, never on any
Create/Update schema.
"""
from pydantic import BaseModel, ConfigDict, Field, field_validator
from typing import Optional, Dict, Any, List
from uuid import UUID
from datetime import datetime

from database_utils.models.isp import ClientServiceStatus, PURPOSE_ACTIVATION, SuspensionReason
from database_utils.models.crm import RecurrenceEnum, RecurringOrderStatus
from .service_plan import ProvisioningParam, ServicePlanOut, _coerce_params
from .topology import normalize_purpose


class ClientServiceBase(BaseModel):
    client_id: UUID
    service_plan_id: UUID
    # D5: replaces network_node_id (removed in revision c2d_graph_removal).
    # Nullable — legacy/non-provisioned services may have none.
    topology_id: Optional[UUID] = None
    connection_params: Optional[Dict[str, Any]] = None
    # Per-service VALUES for the parameters this service's plan declares with
    # scope='service' (doc 33 follow-up). The plan owns the declaration; only
    # the value lives here. Reuses ServicePlan's row model so both sides of the
    # feature validate keys identically; `description`/`scope` are ignored on
    # this side (the declaration is authoritative).
    provisioning_params: Optional[List[ProvisioningParam]] = None
    notes: Optional[str] = None

    @field_validator("provisioning_params", mode="before")
    @classmethod
    def _accept_legacy_param_dict(cls, v):
        return _coerce_params(v)


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
    provisioning_params: Optional[List[ProvisioningParam]] = None
    notes: Optional[str] = None

    @field_validator("provisioning_params", mode="before")
    @classmethod
    def _accept_legacy_param_dict(cls, v):
        return _coerce_params(v)


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
    # Cycle 7 (doc 25 §2.5): install state machine, separate from billing
    # `status`. Read-only — written exclusively by backend-erp's
    # recompute_install_state (link/unlink CPE, acs_sync, worker settlement);
    # deliberately NOT on ClientServiceUpdate.
    install_state: str = "NOT_INSTALLED"
    installed_at: Optional[datetime] = None
    # ba1 (doc 30): attested-adoption fact. Read-only — writable ONLY via the
    # adopt/un-adopt endpoints (client_services.adopt permission); deliberately
    # absent from ClientServiceCreate/Update (migration_source precedent).
    adopted_at: Optional[datetime] = None
    adopted_by_user_id: Optional[UUID] = None
    adoption_note: Optional[str] = None
    # Backend-COMPUTED, not a column: 'provisioned' | 'attested' | None (see
    # models.isp.ACTIVATION_EVIDENCE_VALUES). Populated by backend-erp ONLY on
    # list (batched +2 queries/page), detail, adopt and un-adopt responses;
    # None elsewhere means 'not computed', not 'no evidence'. from_attributes
    # falls back to the default when the ORM attribute is missing.
    activation_evidence: Optional[str] = None

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


class ClientServiceAdoptIn(BaseModel):
    """POST /client-services/{id}/adopt body (doc 30). note is REQUIRED and
    non-empty — an attestation without provenance is worthless. installed_at:
    optional HISTORICAL install date; applied only if the service's
    installed_at is still NULL (a stamped first-install fact is never
    rewritten). topology_id: optional topology to assign DURING adoption
    (service-lifecycle cycle, founder decision 9) — an adopted/brownfield
    service with no topology can run no lifecycle playbook at all, so it would
    be uncancellable except by the admin force escape hatch. Inherited by
    ClientServiceAdoptBulkItem, so the bulk campaign path accepts it too."""
    note: str
    installed_at: Optional[datetime] = None
    topology_id: Optional[UUID] = None

    @field_validator('note')
    @classmethod
    def _note_non_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError('adoption note must be non-empty')
        return v


class ClientServiceAdoptBulkItem(ClientServiceAdoptIn):
    client_service_id: UUID


class ClientServiceAdoptBulkIn(BaseModel):
    """POST /client-services/adopt-bulk body — campaign tooling (doc 30)."""
    items: list[ClientServiceAdoptBulkItem] = Field(min_length=1, max_length=500)


class ClientServiceAdoptBulkRowResult(BaseModel):
    """Per-row outcome — bulk adopt never aborts all-or-nothing (doc 30).
    status 'adopted' | 'error'; error 'NOT_FOUND' | 'ALREADY_ADOPTED'."""
    client_service_id: UUID
    status: str
    error: Optional[str] = None
    install_state: Optional[str] = None


class ClientServiceAdoptBulkOut(BaseModel):
    results: list[ClientServiceAdoptBulkRowResult]
    adopted_count: int = 0
    error_count: int = 0


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
