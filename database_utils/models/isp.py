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
    Uuid, Float, Index, UniqueConstraint
)
from sqlalchemy.orm import relationship, Mapped, mapped_column, validates

from database_utils.database import Base
from ..utils.timezone_utils import now_gt
# Cycle 2 D1 (entity merge): client_service billing reuses these EXISTING PG
# enum types owned by recurring_order — zero new-enum risk (doc 18 §1b).
from .crm import RecurrenceEnum, RecurringOrderStatus

import enum
import uuid


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


class DeviceCategory(str, enum.Enum):
    ROUTER = "ROUTER"
    SWITCH = "SWITCH"
    OLT = "OLT"
    ONU = "ONU"
    SPLITTER = "SPLITTER"
    SPLICE_CLOSURE = "SPLICE_CLOSURE"
    PATCH_PANEL = "PATCH_PANEL"
    ACCESS_POINT = "ACCESS_POINT"
    CPE_ROUTER = "CPE_ROUTER"
    UPS = "UPS"
    ANTENNA = "ANTENNA"
    RADIO = "RADIO"
    OTHER = "OTHER"


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


class ProvisioningTrigger(str, enum.Enum):
    USER = "USER"
    WORKFLOW = "WORKFLOW"
    API = "API"


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

class DeviceType(Base):
    """Per-company equipment catalog entry (vendor/model + typed attribute schema)."""
    __tablename__ = "device_type"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime(timezone=True), nullable=False, default=now_gt)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=now_gt, onupdate=now_gt)
    name = Column(String, nullable=False)
    category = Column(Enum(DeviceCategory), nullable=False, default=DeviceCategory.OTHER)
    vendor = Column(String, nullable=True)   # "Huawei", "ZTE", "MikroTik", ...
    model = Column(String, nullable=True)    # "MA5800-X7", "F660", ...
    description = Column(String, nullable=True)
    # Declarative attribute definitions for items of this type:
    # [{"key": "tx_power_dbm", "label": "TX Power (dBm)", "type": "NUMBER",
    #   "required": false, "options": null, "unit": "dBm"}]
    attribute_schema = Column(JSON, nullable=True)
    default_attributes = Column(JSON, nullable=True)

    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("company.id", ondelete="CASCADE"), nullable=False, index=True
    )

    company = relationship("Company", back_populates="device_types")
    items = relationship("InventoryItem", back_populates="device_type")


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
# Topology (Cycle 2 D5): named ordered chain of device types + bound playbook.
# Replaces the free-form network graph (network_node/network_node_type/
# network_link, removed in revision c2d_graph_removal). Concrete devices
# resolve from the client's assigned inventory by TYPE at provisioning time
# (backend-erp services/provisioning_resolution.py) — no coordinate/graph UI.
# ---------------------------------------------------------------------------

class Topology(Base):
    """A named, ordered chain of device types (e.g. Router -> ONU -> Customer
    Router) bound to the playbook that provisions it end to end."""
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
    # RESTRICT: a topology is bound to the playbook that provisions its chain;
    # mirrors provisioning_job.playbook_id (playbooks.py DELETE already 409s on
    # referencing jobs — the router guard extends to referencing topologies).
    playbook_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("playbook.id", ondelete="RESTRICT"), nullable=False
    )

    company = relationship("Company", back_populates="topologies")
    playbook = relationship("Playbook")
    device_types = relationship(
        "TopologyDeviceType", back_populates="topology",
        cascade="all, delete-orphan", order_by="TopologyDeviceType.position",
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

    topology = relationship("Topology", back_populates="device_types")
    device_type = relationship("DeviceType")

    __table_args__ = (
        UniqueConstraint("topology_id", "position", name="uq_topology_position"),
        # One occurrence of a type per chain: match-by-type resolution (D5) is
        # deterministic only if a type cannot appear twice in the same chain.
        UniqueConstraint("topology_id", "device_type_id", name="uq_topology_device_type"),
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
    target_category = Column(Enum(DeviceCategory), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    definition = Column(JSON, nullable=False)

    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("company.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("user.id", ondelete="SET NULL"), nullable=True
    )

    company = relationship("Company", back_populates="playbooks")
    creator = relationship("User", foreign_keys=[created_by])
    jobs = relationship("ProvisioningJob", back_populates="playbook")


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
        # Duplicate-enqueue guard (e.g. workflow retriggers).
        Index(
            "uq_provisioning_job_company_idem",
            "company_id", "idempotency_key",
            unique=True,
            postgresql_where=text("idempotency_key IS NOT NULL AND status IN ('QUEUED','RUNNING')"),
        ),
    )
