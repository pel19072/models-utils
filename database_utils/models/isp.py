"""
ISP vertical models: service plans, subscriber services, network inventory,
topology, and provisioning automation.

Design rationale: docs/isp-platform/00-architecture-decisions.md (repo root),
docs/isp-platform/18-cycle2-design.md (D1-D10, entity merge + topology rework).
- Hybrid inventory (ADR-002): hot fields as columns, vendor long-tail in
  schema-validated JSONB (`attributes` validated against the catalog's
  `attribute_schema`).
- Topology as an ordered device-type chain (D5, Cycle 2): the free-form
  network graph (network_node/network_node_type/network_link, ADR-003) was
  removed in revision c2d_graph_removal — device kinds are resolved by TYPE
  from a client's assigned inventory, not by a mapped node graph.
- Durable provisioning queue (ADR-005): provisioning_job rows are claimed by
  the worker via SELECT ... FOR UPDATE SKIP LOCKED.
"""
from sqlalchemy import (
    Column, String, Integer, BigInteger, Boolean, JSON, DateTime, ForeignKey, Enum, text,
    Uuid, Float, Index, UniqueConstraint, CheckConstraint, LargeBinary
)
from sqlalchemy.orm import relationship, Mapped, mapped_column, validates

from database_utils.database import Base
from ..utils.timezone_utils import now_gt, make_aware_gt
# Cycle 2 D1 (entity merge): client_service billing reuses these EXISTING PG
# enum types owned by recurring_order — zero new-enum risk (doc 18 §1b).
from .crm import RecurrenceEnum, RecurringOrderStatus

import enum
import uuid
from typing import Optional


# ---------------------------------------------------------------------------
# Enums (only for closed, state-machine-like sets; open sets are config rows)
# ---------------------------------------------------------------------------

class ServicePlanType(str, enum.Enum):
    FIBER = "FIBER"
    CABLE = "CABLE"
    WIRELESS = "WIRELESS"
    DSL = "DSL"
    OTHER = "OTHER"


class CatalogKind(str, enum.Enum):
    """Cycle 2 entity merge (D1/D2): what a ServicePlan bills FOR. Drives
    Order.order_type derivation (utils/order_typing.py) — INSTALLATION-kind
    items make an order an install work order regardless of plan_type."""
    SERVICE = "SERVICE"
    INSTALLATION = "INSTALLATION"
    HARDWARE = "HARDWARE"


class ClientServiceStatus(str, enum.Enum):
    PENDING_INSTALL = "PENDING_INSTALL"
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    CANCELLED = "CANCELLED"


class SuspensionReason(str, enum.Enum):
    NON_PAYMENT = "NON_PAYMENT"
    CUSTOMER_REQUEST = "CUSTOMER_REQUEST"
    MAINTENANCE = "MAINTENANCE"
    FRAUD = "FRAUD"
    OTHER = "OTHER"


# Cycle 3 E4 (revision c3b_device_categories): the `devicecategory` PG enum
# that used to live here is GONE — DeviceCategory is now a table-backed model
# (see the "Inventory" section below, right before DeviceType, which is its
# first consumer). The class name is deliberately reused so any stray
# pre-Cycle-3 usage (e.g. `DeviceCategory.OTHER`) fails loudly at import/
# attribute-access time instead of silently degrading.

# Cycle 3 E1 (revision c3a_topology_purpose): canonical topology-playbook
# purposes. Plain strings, NOT a PG enum — tenants may define custom purposes
# (uppercase snake, CHECK-enforced in the topology_playbook table). Integrity
# is enforced instead by a DB CHECK constraint, UNIQUE(topology_id, purpose),
# and the shared Pydantic normalizer (schemas/topology.py: strip -> upper ->
# regex). These constants are the single source of truth shared by models,
# the workflow engine (ENQUEUE_PROVISIONING use_topology mode), and seeds.
PURPOSE_ACTIVATION = 'ACTIVATION'
PURPOSE_SUSPENSION = 'SUSPENSION'
PURPOSE_REACTIVATION = 'REACTIVATION'
PURPOSE_DEPROVISION = 'DEPROVISION'
CANONICAL_TOPOLOGY_PURPOSES = (
    PURPOSE_ACTIVATION, PURPOSE_SUSPENSION, PURPOSE_REACTIVATION, PURPOSE_DEPROVISION
)
TOPOLOGY_PURPOSE_PATTERN = r'^[A-Z][A-Z0-9_]{0,49}$'


class InventoryItemStatus(str, enum.Enum):
    IN_STOCK = "IN_STOCK"
    RESERVED = "RESERVED"
    INSTALLED = "INSTALLED"
    IN_REPAIR = "IN_REPAIR"
    RETIRED = "RETIRED"
    LOST = "LOST"


class InventoryItemCondition(str, enum.Enum):
    NEW = "NEW"
    USED = "USED"
    REFURBISHED = "REFURBISHED"
    DAMAGED = "DAMAGED"


class EquipmentEventType(str, enum.Enum):
    RECEIVED = "RECEIVED"
    TRANSFERRED = "TRANSFERRED"
    RESERVED = "RESERVED"
    INSTALLED = "INSTALLED"
    REPLACED = "REPLACED"
    REMOVED = "REMOVED"
    REPAIRED = "REPAIRED"
    RETIRED = "RETIRED"
    MAINTENANCE = "MAINTENANCE"


class ProvisioningJobStatus(str, enum.Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    ROLLED_BACK = "ROLLED_BACK"
    CANCELLED = "CANCELLED"
    # Cycle 5 Phase 1 (network config, canon C2, revision nc1a): the job parks
    # when a TR-069 connection-request task returns 202; the worker slot is
    # released and a poller settles the parked step (pending_step_index) once
    # the inform arrives. Added to the PG enum via ALTER TYPE ADD VALUE in an
    # autocommit block (nc1a) — see the migration docstring.
    PENDING_INFORM = "PENDING_INFORM"


class ProvisioningTrigger(str, enum.Enum):
    USER = "USER"
    WORKFLOW = "WORKFLOW"
    API = "API"


# ---------------------------------------------------------------------------
# Cycle 5 Phase 1 (network configuration / GenieACS-TR069). Plan:
# docs/isp-platform/23-network-config-implementation-plan.md §2; canonical
# conventions register C1–C20. Open, driver-bounded value sets are
# CHECK-constrained strings, NOT PG enums (c3a/c3b precedent) — adding a value
# is a plain transactional ALTER of the CHECK constraint, never the
# ALTER TYPE ... ADD VALUE autocommit dance.
# ---------------------------------------------------------------------------

# canon C19: credential kinds — an OPEN set bounded by driver support (grows by
# phase: tr069 P1; ssh/telnet/snmp P2; agent protocols P3).
CREDENTIAL_KINDS = (
    "SSH", "TELNET", "SNMP_COMMUNITY", "TR069_CONNECTION_REQUEST",
    "HTTP_BASIC", "HTTP_BEARER", "WIREGUARD", "AGENT",
)

# canon C9: network-access transport shape.
NETWORK_ACCESS_KINDS = ("acs", "olt")
NETWORK_ACCESS_MODES = ("direct", "vpn", "tunnel")

# canon C13: derived acs_device_registration ONLINE-vs-STALE threshold (a
# registration that has not informed within this window reads STALE).
ACS_STALE_AFTER_SECONDS = 900

# SQL fragments reused by both the model CheckConstraints below and the
# hand-written nc1a migration — kept as strings so both agree byte-for-byte.
_CREDENTIAL_KIND_CHECK = "kind IN ('SSH','TELNET','SNMP_COMMUNITY','TR069_CONNECTION_REQUEST','HTTP_BASIC','HTTP_BEARER','WIREGUARD','AGENT')"
_NETWORK_ACCESS_KIND_CHECK = "kind IN ('acs','olt')"
_NETWORK_ACCESS_MODE_CHECK = "mode IN ('direct','vpn','tunnel')"


# ---------------------------------------------------------------------------
# Cycle 7 (core network configuration, doc 25 §2, revision nc2a_core_config).
# Same c3a/c3b/nc1a precedent: every new value set is a CHECK-constrained
# string, never a PG enum. The SQL fragments below are shared byte-for-byte
# with the hand-written nc2a migration (the _CREDENTIAL_KIND_CHECK pattern).
# ---------------------------------------------------------------------------

# doc 25 §2.1: the CORE/EDGE axis on device categories. CORE = shared
# infrastructure devices (one physical device serves many subscribers, pinned
# per topology position via topology_device_type.inventory_item_id); EDGE =
# per-subscriber CPE resolved from the client's assigned inventory. NULL =
# passives/unclassified (splitters, patch panels, ...).
DEVICE_CATEGORY_TIERS = ("CORE", "EDGE")

# doc 25 §2.3: transports the generic netmiko CLI drivers speak (Phase 2).
# Lowercase on purpose — these are driver keys, matching the playbook step
# `driver` values, not display strings.
CLI_PROTOCOLS = ("ssh", "telnet")

# doc 25 §2.5: subscriber install state machine on client_service — separate
# from billing `status` by founder decision (2026-07-17 #2). Monotonic upward
# except unlink-cpe may regress to NOT_INSTALLED; first INSTALLED stamps
# installed_at and auto-transitions status PENDING_INSTALL -> ACTIVE
# (backend-erp utils/install_state.py owns the recompute).
INSTALL_STATES = ("NOT_INSTALLED", "IN_PROGRESS", "INSTALLED")

_DEVICE_CATEGORY_TIER_CHECK = "tier IN ('CORE','EDGE')"
_CLI_PROTOCOL_CHECK = "cli_protocol IN ('ssh','telnet')"
_INSTALL_STATE_CHECK = "install_state IN ('NOT_INSTALLED','IN_PROGRESS','INSTALLED')"


class InsightChartType(str, enum.Enum):
    NUMBER = "NUMBER"
    BAR = "BAR"
    PIE = "PIE"


# ---------------------------------------------------------------------------
# Service catalog & subscriptions
# ---------------------------------------------------------------------------

class ServicePlan(Base):
    __tablename__ = "service_plan"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime(timezone=True), nullable=False, default=now_gt)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=now_gt, onupdate=now_gt)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    plan_type = Column(Enum(ServicePlanType), nullable=False, default=ServicePlanType.FIBER)
    download_mbps = Column(Integer, nullable=True)
    upload_mbps = Column(Integer, nullable=True)
    data_cap_gb = Column(Integer, nullable=True)  # NULL = unlimited
    price = Column(Float, nullable=False, default=0.0)
    # Money-in-cents shadow column (Cycle 1 dual-write; Float `price` drops in
    # Cycle 2). Nullable, no server_default — doc 16 §1/§2.2.
    price_cents = Column(BigInteger, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    # Vendor-agnostic provisioning intent consumed as playbook variables,
    # e.g. {"speed_profile": "HOME_50M", "vlan": 110, "qos_class": "residential"}
    provisioning_params = Column(JSON, nullable=True)
    # Cycle 2 entity merge (D1/D2): what this plan bills for. NOT NULL with a
    # server_default so the additive c2a migration never blocks on existing
    # rows; drives Order.order_type derivation (utils/order_typing.py).
    kind = Column(
        Enum(CatalogKind), nullable=False,
        default=CatalogKind.SERVICE, server_default='SERVICE'
    )
    # Absorbed from Product (Cycle 2 D1). NULL = not stock-tracked (SERVICE/
    # INSTALLATION plans typically have no stock concept).
    stock = Column(Integer, nullable=True)
    # Dedicated migration marker (doc 18 amendment 1) — NEVER a JSON field,
    # NEVER exposed on Update schemas. 'c2a' = inserted by the c2a backfill.
    # Used by c2a's downgrade to delete ONLY rows it created.
    migration_source = Column(String, nullable=True)

    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("company.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Billing bridge: the Product SKU this plan bills through (recurring orders).
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("product.id", ondelete="SET NULL"), nullable=True
    )
    # D5: pre-fills a new service's topology so the tech only picks on
    # exceptions. SET NULL — a plan must never block deleting a topology.
    default_topology_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("topology.id", ondelete="SET NULL"), nullable=True
    )

    company = relationship("Company", back_populates="service_plans")
    product = relationship("Product")
    default_topology = relationship("Topology", foreign_keys=[default_topology_id])
    client_services = relationship("ClientService", back_populates="service_plan")

    __table_args__ = (
        # Makes the c2a Product->ServicePlan billing bridge deterministic (one
        # plan per product). Created by revision c2a_catalog_merge.
        Index(
            "uq_service_plan_product", "product_id",
            unique=True, postgresql_where=text("product_id IS NOT NULL"),
        ),
    )


class ClientService(Base):
    """A subscriber's service instance: client x plan x network attachment."""
    __tablename__ = "client_service"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime(timezone=True), nullable=False, default=now_gt)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=now_gt, onupdate=now_gt)
    status = Column(
        Enum(ClientServiceStatus), nullable=False,
        default=ClientServiceStatus.PENDING_INSTALL, server_default='PENDING_INSTALL'
    )
    activation_date = Column(DateTime(timezone=True), nullable=True)
    cancelled_at = Column(DateTime(timezone=True), nullable=True)
    # Connection long-tail: {"pppoe_user": "...", "static_ip": "...", "onu_port": 2}
    connection_params = Column(JSON, nullable=True)
    notes = Column(String, nullable=True)
    # Cycle 5 Phase 1 (functionality F1.4/F2.3, revision nc1a): learned network
    # identifiers written by the provisioning executor at job settlement
    # ({"ont_id": ..., "service_port_ids": [...], "vlan": ..., ...}). Read back
    # as template variables by suspension/reactivation/deprovision playbooks —
    # without it, teardown cannot know which service-ports to delete. JSON:
    # shape varies by vendor/topology, read whole at render time (ADR-002).
    provisioning_state = Column(JSON, nullable=True)
    # Cycle 7 (doc 25 §2.5, revision nc2a_core_config): install state machine,
    # deliberately SEPARATE from billing `status` (founder decision 2026-07-17
    # #2). CHECK-constrained string (INSTALL_STATES), never a PG enum. Written
    # exclusively by backend-erp's recompute_install_state — routers/workflows
    # must not PATCH it directly (not exposed on Update schemas).
    install_state = Column(
        String(20), nullable=False,
        default=INSTALL_STATES[0], server_default='NOT_INSTALLED'
    )
    # Stamped on the FIRST transition to INSTALLED (never cleared by a later
    # regression to NOT_INSTALLED — a historical fact, like activation_date).
    installed_at = Column(DateTime(timezone=True), nullable=True)

    # --- Cycle 2 D1 billing absorption (client_service absorbs recurring_order) ---
    # NULL recurrence/billing_status = billing not configured on this service
    # (legacy/unmigrated or a non-billed attachment). Reuses the EXISTING
    # recurrenceenum/recurringorderstatus PG enum types owned by recurring_order
    # — zero new-enum risk, values copied verbatim (doc 18 amendment, §1b).
    recurrence = Column(Enum(RecurrenceEnum), nullable=True)
    recurrence_end = Column(DateTime(timezone=True), nullable=True)
    # The billing anchor: next charge date. Cycle arithmetic keys off this
    # exactly as RecurringOrderService does today.
    next_generation_date = Column(DateTime(timezone=True), nullable=True)
    last_generated_at = Column(DateTime(timezone=True), nullable=True)
    billing_status = Column(Enum(RecurringOrderStatus), nullable=True)
    quantity = Column(Integer, nullable=False, default=1, server_default='1')
    # Dedicated migration marker (doc 18 amendment 1) — NEVER JSON (the old
    # connection_params-based marker was user-writable and got clobbered by
    # whole-object PATCHes). NEVER exposed on Update schemas. 'c2b' = a
    # client_service materialized by the c2b Pass-2 backfill.
    migration_source = Column(String, nullable=True)

    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("company.id", ondelete="CASCADE"), nullable=False, index=True
    )
    client_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("client.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # RESTRICT: a plan with live subscriptions cannot be deleted (history matters).
    service_plan_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("service_plan.id", ondelete="RESTRICT"), nullable=False
    )
    # D5: named chain of device types + bound playbook. RESTRICT — deleting a
    # topology in use is a 409, never a silent unlink (replaces network_node_id,
    # dropped in c2d_graph_removal).
    topology_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("topology.id", ondelete="RESTRICT"), nullable=True
    )
    # Billing link into the legacy recurring-order engine. Still dual-written
    # during the Cycle-2 rollback window (doc 18 amendment 1) but is NEVER
    # PATCHable — it is migration-critical bridge state, not user data.
    recurring_order_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("recurring_order.id", ondelete="SET NULL"), nullable=True
    )

    company = relationship("Company", back_populates="client_services")
    client = relationship("Client", back_populates="services")
    service_plan = relationship("ServicePlan", back_populates="client_services")
    topology = relationship("Topology", back_populates="client_services")
    recurring_order = relationship("RecurringOrder")
    suspensions = relationship(
        "ServiceSuspension", back_populates="client_service", cascade="all, delete-orphan"
    )
    equipment = relationship("InventoryItem", back_populates="client_service")

    __table_args__ = (
        Index("ix_client_service_company_status", "company_id", "status"),
        Index("ix_client_service_topology_id", "topology_id"),
        # The cron due-scan replacement for ix_recurring_order_status_company
        # (revision c2b_service_billing).
        Index(
            "ix_client_service_billing_due",
            "billing_status", "company_id", "next_generation_date",
        ),
        # Cycle 7 (doc 25 §2.5): services-page install-state badge filter scan.
        Index("ix_client_service_company_install_state", "company_id", "install_state"),
        CheckConstraint(_INSTALL_STATE_CHECK, name="ck_client_service_install_state"),
    )

    @validates("status")
    def _stamp_status_dates(self, key, value):
        """Domain rule enforced at the model so every writer (router, workflow
        engine UPDATE_FIELD, worker) behaves identically: first transition to
        ACTIVE stamps activation_date; CANCELLED stamps cancelled_at."""
        new_status = value.value if isinstance(value, ClientServiceStatus) else value
        if new_status == ClientServiceStatus.ACTIVE.value and self.activation_date is None:
            self.activation_date = now_gt()
        elif new_status == ClientServiceStatus.CANCELLED.value and self.cancelled_at is None:
            self.cancelled_at = now_gt()
        return value


class ServiceSuspension(Base):
    """Suspension history: one row per suspension episode (reactivated_at NULL = ongoing)."""
    __tablename__ = "service_suspension"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime(timezone=True), nullable=False, default=now_gt)
    suspended_at = Column(DateTime(timezone=True), nullable=False, default=now_gt)
    reactivated_at = Column(DateTime(timezone=True), nullable=True)
    reason = Column(Enum(SuspensionReason), nullable=False, default=SuspensionReason.OTHER)
    note = Column(String, nullable=True)

    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("company.id", ondelete="CASCADE"), nullable=False, index=True
    )
    client_service_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("client_service.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("user.id", ondelete="SET NULL"), nullable=True
    )

    client_service = relationship("ClientService", back_populates="suspensions")
    creator = relationship("User", foreign_keys=[created_by])


# ---------------------------------------------------------------------------
# Inventory (ADR-002 hybrid)
# ---------------------------------------------------------------------------

class DeviceCategory(Base):
    """Platform-global device category (Cycle 3 E4, revision
    c3b_device_categories). Replaces the `devicecategory` PG enum with a
    super-admin-managed table (no company_id — SaaS staff own this list,
    tenants read it) so adding a category never requires a migration. `key`
    is the byte-identical successor to the old enum member names (ROUTER,
    SWITCH, ... OTHER) and is immutable after creation (enforced in
    schemas/device_category.py, not here — PG can't cheaply enforce
    immutability). `device_type.category` / `playbook.target_category` keep
    serializing this string via a model @property, so API response shapes
    barely change across the enum->FK migration."""
    __tablename__ = "device_category"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    key = Column(String(50), nullable=False, unique=True)
    name = Column(String(100), nullable=False)
    sort_order = Column(Integer, nullable=False, default=0, server_default='0')
    icon = Column(String(50), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True, server_default='true')
    is_system = Column(Boolean, nullable=False, default=False, server_default='false')
    # Cycle 7 (doc 25 §2.1, revision nc2a_core_config): the CORE/EDGE axis.
    # CHECK-constrained string (DEVICE_CATEGORY_TIERS), NULL = passives/
    # unclassified. SaaS-admin editable like name/icon (key stays immutable);
    # nc2a backfills CORE <- ROUTER/SWITCH/OLT, EDGE <- ONU/CPE_ROUTER/
    # ACCESS_POINT by key.
    tier = Column(String(10), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=now_gt)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=now_gt, onupdate=now_gt)

    __table_args__ = (
        CheckConstraint(_DEVICE_CATEGORY_TIER_CHECK, name="ck_device_category_tier"),
    )


class DeviceType(Base):
    """Per-company equipment catalog entry (vendor/model + typed attribute schema)."""
    __tablename__ = "device_type"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime(timezone=True), nullable=False, default=now_gt)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=now_gt, onupdate=now_gt)
    name = Column(String, nullable=False)
    # Cycle 3 E4: FK replacing the `devicecategory` enum (revision
    # c3b_device_categories, enum -> FK backfill by key match). NOT NULL —
    # every device_type had a (possibly OTHER) category under the enum.
    category_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("device_category.id", ondelete="RESTRICT"), nullable=False
    )
    vendor = Column(String, nullable=True)   # "Huawei", "ZTE", "MikroTik", ...
    model = Column(String, nullable=True)    # "MA5800-X7", "F660", ...
    description = Column(String, nullable=True)
    # Declarative attribute definitions for items of this type:
    # [{"key": "tx_power_dbm", "label": "TX Power (dBm)", "type": "NUMBER",
    #   "required": false, "options": null, "unit": "dBm"}]
    attribute_schema = Column(JSON, nullable=True)
    default_attributes = Column(JSON, nullable=True)
    # Cycle 5 Phase 1 (canon C6, revision nc1a): the device-group provisioning
    # opt-out gate. Default TRUE — the tenant provisioning_settings row is the
    # master switch; this flag lets a tenant exclude gear it never wants
    # touched. Live jobs against a disabled type are rejected 409 at creation.
    provisioning_enabled = Column(Boolean, nullable=False, default=True, server_default='true')
    # Cycle 7 (doc 25 §2.2, revision nc2a_core_config): netmiko platform id
    # for the generic CLI drivers ('huawei_smartax', 'cisco_ios',
    # 'mikrotik_routeros', ...). NULL -> drivers fall back to 'generic' /
    # 'generic_telnet'. Free string on purpose (netmiko's platform list is an
    # open set that grows with netmiko releases — never CHECK-bound it).
    cli_platform = Column(String(50), nullable=True)

    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("company.id", ondelete="CASCADE"), nullable=False, index=True
    )

    company = relationship("Company", back_populates="device_types")
    items = relationship("InventoryItem", back_populates="device_type")
    # lazy='joined': keeps list endpoints, topology chain reads, and
    # provisioning resolution free of N+1 while preserving the `.category`
    # string surface below (doc 20a E4 §2).
    category_ref = relationship("DeviceCategory", lazy="joined")

    @property
    def category(self) -> Optional[str]:
        """String key surface preserved across the enum->FK migration (Cycle
        3 E4) — routers/resolution keep reading a plain string."""
        return self.category_ref.key if self.category_ref else None


class Warehouse(Base):
    __tablename__ = "warehouse"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime(timezone=True), nullable=False, default=now_gt)
    name = Column(String, nullable=False)
    address = Column(String, nullable=True)
    is_vehicle = Column(Boolean, nullable=False, default=False)  # truck stock
    notes = Column(String, nullable=True)

    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("company.id", ondelete="CASCADE"), nullable=False, index=True
    )

    company = relationship("Company", back_populates="warehouses")
    items = relationship("InventoryItem", back_populates="warehouse")


class InventoryItem(Base):
    """A serialized (or bulk) asset. Hot fields are columns; vendor long-tail
    lives in `attributes`, validated against device_type.attribute_schema."""
    __tablename__ = "inventory_item"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime(timezone=True), nullable=False, default=now_gt)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=now_gt, onupdate=now_gt)
    serial_number = Column(String, nullable=True)
    mac_address = Column(String, nullable=True)
    # Cycle 5 Phase 1 (canon C13/F1.2, revision nc1a): device-identity half that
    # pairs with serial_number for the acs_device_registration match. Nullable
    # — populated by UI/import tooling, no automated backfill from attributes.
    oui = Column(String, nullable=True)
    status = Column(
        Enum(InventoryItemStatus), nullable=False,
        default=InventoryItemStatus.IN_STOCK, server_default='IN_STOCK'
    )
    condition = Column(
        Enum(InventoryItemCondition), nullable=False,
        default=InventoryItemCondition.NEW, server_default='NEW'
    )
    attributes = Column(JSON, nullable=True)
    purchase_date = Column(DateTime(timezone=True), nullable=True)
    warranty_until = Column(DateTime(timezone=True), nullable=True)
    cost = Column(Float, nullable=True)
    # Money-in-cents shadow column (Cycle 1 dual-write; Float `cost` drops in
    # Cycle 2). NULL stays NULL in the backfill — doc 16 §2.5.3.
    cost_cents = Column(BigInteger, nullable=True)
    notes = Column(String, nullable=True)
    # --- Cycle 7 management surface (doc 25 §2.3, revision nc2a_core_config) ---
    # How the CLI drivers reach a CORE-tier device. mgmt_port NULL -> driver
    # default (22 ssh / 23 telnet); cli_protocol is a CHECK-constrained string
    # (CLI_PROTOCOLS) selecting which driver the connectivity probe uses.
    mgmt_host = Column(String, nullable=True)
    mgmt_port = Column(Integer, nullable=True)
    cli_protocol = Column(String, nullable=True)
    # Stamped by the provisioning worker when a core_connectivity_check job
    # reaches a terminal state (ok = status SUCCEEDED). Read-only in the API.
    mgmt_last_check_at = Column(DateTime(timezone=True), nullable=True)
    mgmt_last_check_ok = Column(Boolean, nullable=True)

    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("company.id", ondelete="CASCADE"), nullable=False, index=True
    )
    device_type_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("device_type.id", ondelete="RESTRICT"), nullable=False
    )
    warehouse_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("warehouse.id", ondelete="SET NULL"), nullable=True
    )
    # Customer-premise assignment (CPE): who has this item installed.
    client_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("client.id", ondelete="SET NULL"), nullable=True
    )
    client_service_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("client_service.id", ondelete="SET NULL"), nullable=True
    )

    company = relationship("Company", back_populates="inventory_items")
    device_type = relationship("DeviceType", back_populates="items")
    warehouse = relationship("Warehouse", back_populates="items")
    client = relationship("Client", back_populates="equipment")
    client_service = relationship("ClientService", back_populates="equipment")
    events = relationship(
        "EquipmentEvent", back_populates="item",
        cascade="all, delete-orphan", foreign_keys="EquipmentEvent.item_id",
    )

    __table_args__ = (
        # Serial uniqueness per company (only when a serial is recorded).
        Index(
            "uq_inventory_item_company_serial",
            "company_id", "serial_number",
            unique=True,
            postgresql_where=text("serial_number IS NOT NULL"),
        ),
        Index("ix_inventory_item_company_status", "company_id", "status"),
        # Cycle 7 (doc 25 §2.3).
        CheckConstraint(_CLI_PROTOCOL_CHECK, name="ck_inventory_item_cli_protocol"),
    )


class EquipmentEvent(Base):
    """Append-only lifecycle ledger: replacement history, installs, transfers,
    maintenance — with technician attribution."""
    __tablename__ = "equipment_event"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime(timezone=True), nullable=False, default=now_gt)
    event_type = Column(Enum(EquipmentEventType), nullable=False)
    notes = Column(String, nullable=True)
    event_metadata = Column(JSON, nullable=True)

    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("company.id", ondelete="CASCADE"), nullable=False, index=True
    )
    item_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("inventory_item.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Replacement pairing: the item that replaced / was replaced by this one.
    related_item_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("inventory_item.id", ondelete="SET NULL"), nullable=True
    )
    from_warehouse_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("warehouse.id", ondelete="SET NULL"), nullable=True
    )
    to_warehouse_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("warehouse.id", ondelete="SET NULL"), nullable=True
    )
    client_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("client.id", ondelete="SET NULL"), nullable=True
    )
    client_service_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("client_service.id", ondelete="SET NULL"), nullable=True
    )
    technician_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("user.id", ondelete="SET NULL"), nullable=True
    )

    item = relationship("InventoryItem", back_populates="events", foreign_keys=[item_id])
    related_item = relationship("InventoryItem", foreign_keys=[related_item_id])
    technician = relationship("User", foreign_keys=[technician_id])


# ---------------------------------------------------------------------------
# Topology (Cycle 2 D5, purpose-keyed playbooks added Cycle 3 E1): named
# ordered chain of device types + purpose -> playbook map (TopologyPlaybook).
# Replaces the free-form network graph (network_node/network_node_type/
# network_link, removed in revision c2d_graph_removal). Concrete devices
# resolve from the client's assigned inventory by TYPE at provisioning time
# (database_utils/utils/provisioning_resolution.py — moved in from backend-erp
# services/provisioning_resolution.py, Cycle 3 E2) — no coordinate/graph UI.
# ---------------------------------------------------------------------------

class Topology(Base):
    """A named, ordered chain of device types (e.g. Router -> ONU -> Customer
    Router) with purpose-keyed playbooks (Cycle 3 E1, revision
    c3a_topology_purpose — replaces the single playbook_id/playbook shape;
    the pre-c3a playbook_id migrates as this topology's ACTIVATION entry).

    Invariant: every topology has an ACTIVATION entry (enforced in
    schemas/router, not the DB — relied on by the c3a downgrade, which is
    total only when every topology has exactly one to restore playbook_id
    from)."""
    __tablename__ = "topology"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime(timezone=True), nullable=False, default=now_gt)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=now_gt, onupdate=now_gt)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True, server_default='true')

    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("company.id", ondelete="CASCADE"), nullable=False, index=True
    )

    company = relationship("Company", back_populates="topologies")
    device_types = relationship(
        "TopologyDeviceType", back_populates="topology",
        cascade="all, delete-orphan", order_by="TopologyDeviceType.position",
    )
    # Cycle 3 E1: purpose -> playbook map (topology_playbook). Ordered by
    # purpose so ACTIVATION (alphabetically first among the canonical set)
    # renders first in list contexts.
    playbooks = relationship(
        "TopologyPlaybook", back_populates="topology",
        cascade="all, delete-orphan", order_by="TopologyPlaybook.purpose",
    )
    client_services = relationship("ClientService", back_populates="topology")

    __table_args__ = (
        UniqueConstraint("company_id", "name", name="uq_topology_company_name"),
    )


class TopologyDeviceType(Base):
    """One position in a topology's device chain. `position` is 0-based
    provisioning order (router first, CPE last)."""
    __tablename__ = "topology_device_type"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime(timezone=True), nullable=False, default=now_gt)
    position = Column(Integer, nullable=False)

    topology_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("topology.id", ondelete="CASCADE"), nullable=False
    )
    # RESTRICT: a device type referenced by a topology chain cannot be deleted
    # out from under it (matches inventory_item.device_type_id RESTRICT).
    device_type_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("device_type.id", ondelete="RESTRICT"), nullable=False
    )
    # Cycle 7 (doc 25 §2.4, revision nc2a_core_config): pins the concrete
    # SHARED device serving this chain position (e.g. this topology's OLT).
    # Pinned items are exempt from client/service candidate matching in
    # provisioning resolution (§3 — shared infrastructure, not CPE). SET NULL:
    # retiring the item must never block, resolution then fails visibly with
    # MISSING_DEVICE. Same-company + device_type match + CORE-tier category
    # are router/schema validation, not DB constraints (doc 25 §2.4).
    inventory_item_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("inventory_item.id", ondelete="SET NULL"), nullable=True, index=True
    )

    topology = relationship("Topology", back_populates="device_types")
    device_type = relationship("DeviceType")
    inventory_item = relationship("InventoryItem")

    __table_args__ = (
        UniqueConstraint("topology_id", "position", name="uq_topology_position"),
        # One occurrence of a type per chain: match-by-type resolution (D5) is
        # deterministic only if a type cannot appear twice in the same chain.
        UniqueConstraint("topology_id", "device_type_id", name="uq_topology_device_type"),
    )


class TopologyPlaybook(Base):
    """One purpose -> playbook binding for a topology (Cycle 3 E1, revision
    c3a_topology_purpose). A single Playbook may serve as e.g. ACTIVATION for
    topology A and REACTIVATION for topology B — purpose is a property of the
    binding, not of the Playbook itself (Playbook is unchanged)."""
    __tablename__ = "topology_playbook"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime(timezone=True), nullable=False, default=now_gt)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=now_gt, onupdate=now_gt)

    topology_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("topology.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Uppercase snake; canonical set in CANONICAL_TOPOLOGY_PURPOSES, but
    # tenants may define custom purposes (CHECK-enforced, not enum-enforced).
    purpose = Column(String(50), nullable=False)
    # RESTRICT mirrors provisioning_job.playbook_id; playbooks.py's DELETE
    # guard counts these rows (distinct topology_id) alongside jobs.
    playbook_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("playbook.id", ondelete="RESTRICT"), nullable=False, index=True
    )

    topology = relationship("Topology", back_populates="playbooks")
    playbook = relationship("Playbook")

    __table_args__ = (
        UniqueConstraint("topology_id", "purpose", name="uq_topology_playbook_purpose"),
        CheckConstraint("purpose ~ '^[A-Z][A-Z0-9_]{0,49}$'", name="ck_topology_playbook_purpose_format"),
    )


# ---------------------------------------------------------------------------
# Provisioning automation (ADR-005/006)
# ---------------------------------------------------------------------------

class Playbook(Base):
    """Declarative, versioned provisioning recipe uploaded by the company.
    `definition` holds: variables (typed schema), steps (driver, template,
    validation, timeout), rollback steps. Validated on upload."""
    __tablename__ = "playbook"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime(timezone=True), nullable=False, default=now_gt)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=now_gt, onupdate=now_gt)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    version = Column(Integer, nullable=False, default=1)
    target_vendor = Column(String, nullable=True)    # "huawei", "zte", "mikrotik", ...
    # Cycle 3 E4: FK replacing the `devicecategory` enum (revision
    # c3b_device_categories, enum -> FK backfill by key match). Stays
    # nullable — a playbook need not target a specific category. RESTRICT:
    # categories carry referential meaning (per doc 20a admin-categories §1).
    target_category_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("device_category.id", ondelete="RESTRICT"), nullable=True
    )
    is_active = Column(Boolean, nullable=False, default=True)
    definition = Column(JSON, nullable=False)
    # Cycle 5 Phase 1 (canon C7, revision nc1a): stamped with `version` when a
    # dry-run ProvisioningJob (dry_run=true) for that version SUCCEEDS. A live
    # job is accepted iff last_dry_run_version == version, else 409
    # DRY_RUN_REQUIRED. The render-only preview endpoint does NOT satisfy this
    # gate; seeded system playbooks are exempt (SaaS-verified in CI).
    last_dry_run_version = Column(Integer, nullable=True)

    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("company.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("user.id", ondelete="SET NULL"), nullable=True
    )

    company = relationship("Company", back_populates="playbooks")
    creator = relationship("User", foreign_keys=[created_by])
    jobs = relationship("ProvisioningJob", back_populates="playbook")
    target_category_ref = relationship("DeviceCategory", lazy="joined")

    @property
    def target_category(self) -> Optional[str]:
        """String key surface preserved across the enum->FK migration (Cycle
        3 E4)."""
        return self.target_category_ref.key if self.target_category_ref else None


class ProvisioningJob(Base):
    """Durable execution queue row. Claimed by the provisioning worker via
    SELECT ... FOR UPDATE SKIP LOCKED; retried with backoff up to max_attempts."""
    __tablename__ = "provisioning_job"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime(timezone=True), nullable=False, default=now_gt)
    status = Column(
        Enum(ProvisioningJobStatus), nullable=False,
        default=ProvisioningJobStatus.QUEUED, server_default='QUEUED'
    )
    attempts = Column(Integer, nullable=False, default=0)
    max_attempts = Column(Integer, nullable=False, default=3)
    idempotency_key = Column(String, nullable=True)
    scheduled_for = Column(DateTime(timezone=True), nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    variables = Column(JSON, nullable=True)      # resolved playbook inputs
    log = Column(JSON, nullable=True)            # per-step structured results
    error = Column(String, nullable=True)
    triggered_by = Column(
        Enum(ProvisioningTrigger), nullable=False,
        default=ProvisioningTrigger.USER, server_default='USER'
    )
    # --- Cycle 5 Phase 1 (network config, revision nc1a) ---
    # canon C7: dry-run jobs never touch a device; a SUCCEEDED dry-run stamps
    # playbook.last_dry_run_version.
    dry_run = Column(Boolean, nullable=False, default=False, server_default='false')
    # canon C2: the parked step to settle when the inform arrives (PENDING_INFORM).
    pending_step_index = Column(Integer, nullable=True)
    # GenieACS NBI task ids being polled on the 202 / connection-request path.
    pending_task_ids = Column(JSON, nullable=True)
    # canon C11: the worker stamps this while RUNNING; the lease reaper re-queues
    # stale RUNNING jobs (Railway redeploys the worker on every merge). The
    # reaper does NOT increment attempts (the claim path already does).
    heartbeat_at = Column(DateTime(timezone=True), nullable=True)
    # canon C11: per-device serialization key. The DB partial unique index below
    # is the serialization authority; in-process locks are a local optimization.
    device_lock_key = Column(String, nullable=True)

    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("company.id", ondelete="CASCADE"), nullable=False, index=True
    )
    playbook_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("playbook.id", ondelete="RESTRICT"), nullable=False
    )
    # Optional targets (what this job provisions).
    client_service_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("client_service.id", ondelete="SET NULL"), nullable=True, index=True
    )
    inventory_item_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("inventory_item.id", ondelete="SET NULL"), nullable=True
    )
    # HTTP-driver credentials/endpoint source.
    integration_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("integration.id", ondelete="SET NULL"), nullable=True
    )
    triggered_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("user.id", ondelete="SET NULL"), nullable=True
    )

    company = relationship("Company", back_populates="provisioning_jobs")
    playbook = relationship("Playbook", back_populates="jobs")
    client_service = relationship("ClientService")
    inventory_item = relationship("InventoryItem")
    integration = relationship("Integration")
    triggered_by_user = relationship("User", foreign_keys=[triggered_by_user_id])

    __table_args__ = (
        # Worker claim scan: QUEUED ordered by created_at.
        Index(
            "ix_provisioning_job_claim",
            "status", "scheduled_for", "created_at",
            postgresql_where=text("status = 'QUEUED'"),
        ),
        # Duplicate-enqueue guard (e.g. workflow retriggers). Cycle 5 Phase 1
        # (canon C2): the in-flight set now includes PENDING_INFORM so a parked
        # job still de-duplicates re-enqueues. The predicate is dropped and
        # recreated in revision nc1a (autogenerate cannot alter a partial index).
        Index(
            "uq_provisioning_job_company_idem",
            "company_id", "idempotency_key",
            unique=True,
            postgresql_where=text(
                "idempotency_key IS NOT NULL AND status IN ('QUEUED','RUNNING','PENDING_INFORM')"
            ),
        ),
        # Cycle 5 Phase 1 (canon C11, revision nc1a): per-device serialization
        # authority — at most one live job per device_lock_key across the
        # in-flight set (QUEUED/RUNNING/PENDING_INFORM).
        Index(
            "uq_provisioning_job_device_lock",
            "device_lock_key",
            unique=True,
            postgresql_where=text(
                "device_lock_key IS NOT NULL AND status IN ('QUEUED','RUNNING','PENDING_INFORM')"
            ),
        ),
    )


# ---------------------------------------------------------------------------
# Network configuration (Cycle 5 Phase 1: TR-069 / GenieACS). Plan:
# docs/isp-platform/23-network-config-implementation-plan.md §2. Envelope-
# encrypted device secrets (device_credential, canon C1/C19), per-tenant
# transport config (network_access, canon C9), serial/OUI -> tenant mapping
# (acs_device_registration, canon C13), the tenant enable gate
# (provisioning_settings, canon C6), and the append-only device audit trail
# (device_action_log, canon C14 — append-only enforced by a Postgres trigger
# created in revision nc1b, not here).
# ---------------------------------------------------------------------------

class NetworkAccess(Base):
    """Per-tenant transport configuration (canon C9). Multiple rows per tenant,
    keyed by `kind` (acs|olt); the transport resolver reads it keyed on
    company_id + the target management address. `kind`/`mode` are
    CHECK-constrained strings (not PG enums) per the c3a/c3b precedent —
    transport modes are config-flavored and grow by phase. WireGuard keys/PSK
    are NOT columns here (Phase 2+): they live in a device_credential row of
    kind WIREGUARD bound via network_access_id (canon C19 — bindings on the
    credential, no credential FK here)."""
    __tablename__ = "network_access"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime(timezone=True), nullable=False, default=now_gt)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=now_gt, onupdate=now_gt)
    name = Column(String, nullable=False)
    kind = Column(String, nullable=False)   # CHECK: acs | olt
    mode = Column(String, nullable=False, default="direct", server_default="direct")  # CHECK
    is_default = Column(Boolean, nullable=False, default=False, server_default="false")
    # Which mgmt addresses this path serves (JSON list of CIDR strings); the
    # resolver does longest-prefix match, else the default row. NULL on the
    # default row. Atomic config value read whole — never queried per-element.
    mgmt_subnets = Column(JSON, nullable=True)
    # Phase-4 per-tenant ACS escape hatch — nullable from day one, unused until P4.
    acs_base_url = Column(String, nullable=True)

    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("company.id", ondelete="CASCADE"), nullable=False, index=True
    )

    company = relationship("Company", back_populates="network_accesses")

    __table_args__ = (
        UniqueConstraint("company_id", "name", name="uq_network_access_company_name"),
        CheckConstraint(_NETWORK_ACCESS_KIND_CHECK, name="ck_network_access_kind"),
        CheckConstraint(_NETWORK_ACCESS_MODE_CHECK, name="ck_network_access_mode"),
        # Exactly one default path per tenant PER KIND (one default ACS, one
        # default OLT).
        Index(
            "uq_network_access_default",
            "company_id", "kind",
            unique=True,
            postgresql_where=text("is_default"),
        ),
    )


class DeviceCredential(Base):
    """Envelope-encrypted per-tenant device secret (canon C1/C19). AES-256-GCM
    with a per-row DEK wrapped by a KEK held in Railway env vars
    (database_utils.utils.crypto). `kind` is a CHECK-constrained string (open
    set, CREDENTIAL_KINDS) — adding a kind is a plain ALTER of the CHECK, never
    an ALTER TYPE. Secrets never round-trip: the Out schema exposes only
    has_secret + fingerprint (last 4).

    Binding FKs live ON this row (canon C19): resolution order at execution is
    inventory_item > device_type > network_access default. No other table
    carries an FK pointing at a credential."""
    __tablename__ = "device_credential"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime(timezone=True), nullable=False, default=now_gt)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=now_gt, onupdate=now_gt)
    name = Column(String, nullable=False)
    kind = Column(String, nullable=False)             # CHECK: CREDENTIAL_KINDS
    username = Column(String, nullable=True)          # display-safe, NOT secret
    # --- envelope encryption (all opaque to SQL; canon C1 column names) ---
    secret_ciphertext = Column(LargeBinary, nullable=False)  # 12-byte nonce prefixed
    dek_wrapped = Column(LargeBinary, nullable=False)        # AES-256-GCM(KEK, DEK)
    kek_id = Column(String, nullable=False)                  # key id into CREDENTIALS_KEKS
    # last 4 chars of a SHA-256 over the plaintext, computed at write time —
    # display-safe, lets the UI confirm which secret is stored without exposing it.
    fingerprint = Column(String, nullable=True)
    last_rotated_at = Column(DateTime(timezone=True), nullable=True)

    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("company.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # --- bindings (canon C19: binding FKs live ON the credential row) ---
    inventory_item_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("inventory_item.id", ondelete="SET NULL"), nullable=True, index=True
    )
    device_type_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("device_type.id", ondelete="SET NULL"), nullable=True, index=True
    )
    network_access_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("network_access.id", ondelete="SET NULL"), nullable=True, index=True
    )

    company = relationship("Company", back_populates="device_credentials")
    inventory_item = relationship("InventoryItem")
    device_type = relationship("DeviceType")
    network_access = relationship("NetworkAccess")

    __table_args__ = (
        UniqueConstraint("company_id", "name", name="uq_device_credential_company_name"),
        CheckConstraint(_CREDENTIAL_KIND_CHECK, name="ck_device_credential_kind"),
    )

    @property
    def has_secret(self) -> bool:
        """Out-schema surface (canon C19): a credential always stores a secret,
        but expose the boolean explicitly so the API never implies the
        ciphertext could be read back."""
        return self.secret_ciphertext is not None


class AcsDeviceRegistration(Base):
    """Serial/OUI -> tenant mapping (canon C13): the tenant-stamping keystone.
    At first inform the GenieACS provision script calls back into Uplink; we
    look up the announcing device here and stamp the tag `t-{company_id}`.

    `company_id` is NULLABLE (NULL = QUARANTINED: informed without
    pre-registration, awaiting superadmin assignment). The (oui, serial_number)
    unique is GLOBAL (no company_id) so two tenants can never claim the same
    physical CPE — cross-tenant duplicate pre-registration is a 409 in the
    router. Status is DERIVED (no enum column), see `state`."""
    __tablename__ = "acs_device_registration"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime(timezone=True), nullable=False, default=now_gt)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=now_gt, onupdate=now_gt)

    company_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("company.id", ondelete="CASCADE"), nullable=True, index=True
    )
    inventory_item_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("inventory_item.id", ondelete="SET NULL"), nullable=True
    )
    serial_number = Column(String, nullable=False)
    oui = Column(String, nullable=True)
    first_inform_at = Column(DateTime(timezone=True), nullable=True)
    last_inform_at = Column(DateTime(timezone=True), nullable=True)
    genieacs_device_id = Column(String, nullable=True)  # "OUI-ProductClass-Serial"
    # per-device CWMP connection-request credentials (canon C13): issued at
    # bootstrap, used by GenieACS connection requests — never blank/blank.
    # Envelope-encrypted via crypto.py (AAD = f"{company_id}:{registration_id}").
    cwmp_cr_username = Column(String, nullable=True)
    cwmp_cr_secret_ciphertext = Column(LargeBinary, nullable=True)
    cwmp_cr_dek_wrapped = Column(LargeBinary, nullable=True)
    cwmp_cr_kek_id = Column(String, nullable=True)

    company = relationship("Company", back_populates="acs_device_registrations")
    inventory_item = relationship("InventoryItem")

    __table_args__ = (
        UniqueConstraint("oui", "serial_number", name="uq_acs_registration_identity"),
    )

    @property
    def state(self) -> str:
        """Derived status (canon C13) — no enum column, matching the
        ServiceSuspension.reactivated_at NULL-episode pattern. Order matters:
        a quarantined device may already have informed, so company_id wins."""
        if self.company_id is None:
            return "QUARANTINED"
        if self.first_inform_at is None:
            return "PRE_REGISTERED"
        if self.last_inform_at is None:
            return "STALE"
        age = (now_gt() - make_aware_gt(self.last_inform_at)).total_seconds()
        return "ONLINE" if age <= ACS_STALE_AFTER_SECONDS else "STALE"


class ProvisioningSettings(Base):
    """Tenant provisioning enable gate — a singleton per tenant (canon C6).
    Absence of a row means DISABLED (fail-safe); the row is created lazily /
    by tenant-onboarding automation, never seeded. Not a column on `company`:
    auth-erp owns that table and this is ISP-module config."""
    __tablename__ = "provisioning_settings"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime(timezone=True), nullable=False, default=now_gt)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=now_gt, onupdate=now_gt)

    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("company.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    # master switch, default OFF (fail-safe).
    enabled = Column(Boolean, nullable=False, default=False, server_default="false")
    # tenant default inform interval (seconds) pushed to CPE presets; NULL = use
    # the platform default.
    default_inform_interval = Column(Integer, nullable=True)

    company = relationship("Company", back_populates="provisioning_settings")


class DeviceActionLog(Base):
    """Append-only device audit trail (canon C14). Distinct from auth's
    AuditLog (super-admin actions) and EquipmentEvent (stock movements). No
    `updated_at` — rows are immutable. Append-only is enforced AT THE DATABASE
    by a BEFORE UPDATE OR DELETE trigger raising an exception, created in the
    hand-written revision nc1b (not here). The app layer exposes read-only
    list/get; writes happen exclusively in the worker/backend service modules."""
    __tablename__ = "device_action_log"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime(timezone=True), nullable=False, default=now_gt)

    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("company.id", ondelete="CASCADE"), nullable=False, index=True
    )
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("user.id", ondelete="SET NULL"), nullable=True
    )
    actor_kind = Column(String, nullable=False)          # user | automation | system
    device_kind = Column(String, nullable=True)          # cpe | olt | ...
    device_identity = Column(String, nullable=True)      # serial or host
    action = Column(String, nullable=False)              # 'ont.add', 'cpe.factory_reset', ...
    before_data = Column(JSON, nullable=True)            # secret-redacted before insert
    after_data = Column(JSON, nullable=True)
    provisioning_job_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("provisioning_job.id", ondelete="SET NULL"), nullable=True
    )
    detail = Column(JSON, nullable=True)

    company = relationship("Company", back_populates="device_action_logs")
    actor = relationship("User", foreign_keys=[actor_user_id])
    provisioning_job = relationship("ProvisioningJob")

    __table_args__ = (
        Index("ix_device_action_log_company_created", "company_id", "created_at"),
    )


# ---------------------------------------------------------------------------
# Insights (Cycle 4): tenant-defined dashboards of simple charts driven off
# existing entities (clients, orders, client_services, ...). No new
# analytics engine — `spec` names an entity/measure/dimension resolved by
# backend-erp's insights service against existing tables. Available to every
# tenant (no tier module gate).
# ---------------------------------------------------------------------------

class InsightDashboard(Base):
    """A named collection of charts (insight_chart), scoped to a company."""
    __tablename__ = "insight_dashboard"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime(timezone=True), nullable=False, default=now_gt)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=now_gt, onupdate=now_gt)
    name = Column(String, nullable=False)
    ordering = Column(Integer, nullable=False, default=0, server_default='0')

    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("company.id", ondelete="CASCADE"), nullable=False, index=True
    )

    company = relationship("Company", back_populates="insight_dashboards")
    charts = relationship(
        "InsightChart", back_populates="dashboard",
        cascade="all, delete-orphan", order_by="InsightChart.ordering",
    )

    __table_args__ = (
        UniqueConstraint("company_id", "name", name="uq_insight_dashboard_company_name"),
    )


class InsightChart(Base):
    """One chart within a dashboard. `spec` (entity/measure/dimension/filters)
    is resolved server-side against the existing schema — no company_id here,
    tenant scope derives via dashboard_id (matches topology_device_type's
    scoping-through-parent pattern)."""
    __tablename__ = "insight_chart"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime(timezone=True), nullable=False, default=now_gt)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=now_gt, onupdate=now_gt)
    title = Column(String, nullable=False)
    chart_type = Column(Enum(InsightChartType), nullable=False)
    # {"entity": "client_service", "measure": "count", "dimension": "status",
    #  "filters": {...}}
    spec = Column(JSON, nullable=False)
    ordering = Column(Integer, nullable=False, default=0, server_default='0')

    dashboard_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("insight_dashboard.id", ondelete="CASCADE"), nullable=False, index=True
    )

    dashboard = relationship("InsightDashboard", back_populates="charts")
