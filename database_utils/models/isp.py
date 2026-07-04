"""
ISP vertical models: service plans, subscriber services, network inventory,
topology, and provisioning automation.

Design rationale: docs/isp-platform/00-architecture-decisions.md (repo root).
- Hybrid inventory (ADR-002): hot fields as columns, vendor long-tail in
  schema-validated JSONB (`attributes` validated against the catalog's
  `attribute_schema`).
- Config-driven topology (ADR-003): node kinds are per-company rows
  (network_node_type), not enums, so new technologies need no migration.
- Durable provisioning queue (ADR-005): provisioning_job rows are claimed by
  the worker via SELECT ... FOR UPDATE SKIP LOCKED.
"""
from sqlalchemy import (
    Column, String, Integer, Boolean, JSON, DateTime, ForeignKey, Enum, text,
    Uuid, Float, Index, UniqueConstraint
)
from sqlalchemy.orm import relationship, Mapped, mapped_column

from database_utils.database import Base
from ..utils.timezone_utils import now_gt

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


class NetworkNodeStatus(str, enum.Enum):
    PLANNED = "PLANNED"
    ACTIVE = "ACTIVE"
    DEGRADED = "DEGRADED"
    DOWN = "DOWN"
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
    is_active = Column(Boolean, nullable=False, default=True)
    # Vendor-agnostic provisioning intent consumed as playbook variables,
    # e.g. {"speed_profile": "HOME_50M", "vlan": 110, "qos_class": "residential"}
    provisioning_params = Column(JSON, nullable=True)

    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("company.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Billing bridge: the Product SKU this plan bills through (recurring orders).
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("product.id", ondelete="SET NULL"), nullable=True
    )

    company = relationship("Company", back_populates="service_plans")
    product = relationship("Product")
    client_services = relationship("ClientService", back_populates="service_plan")


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
    # The subscriber's attachment point in the topology (usually their ONU/CPE node).
    network_node_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("network_node.id", ondelete="SET NULL"), nullable=True
    )
    # Billing link into the existing recurring-order engine.
    recurring_order_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("recurring_order.id", ondelete="SET NULL"), nullable=True
    )

    company = relationship("Company", back_populates="client_services")
    client = relationship("Client", back_populates="services")
    service_plan = relationship("ServicePlan", back_populates="client_services")
    network_node = relationship("NetworkNode", back_populates="client_services")
    recurring_order = relationship("RecurringOrder")
    suspensions = relationship(
        "ServiceSuspension", back_populates="client_service", cascade="all, delete-orphan"
    )
    equipment = relationship("InventoryItem", back_populates="client_service")

    __table_args__ = (
        Index("ix_client_service_company_status", "company_id", "status"),
    )


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
    # Infrastructure placement: the topology node this asset fulfills.
    network_node_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("network_node.id", ondelete="SET NULL"), nullable=True
    )

    company = relationship("Company", back_populates="inventory_items")
    device_type = relationship("DeviceType", back_populates="items")
    warehouse = relationship("Warehouse", back_populates="items")
    client = relationship("Client", back_populates="equipment")
    client_service = relationship("ClientService", back_populates="equipment")
    network_node = relationship(
        "NetworkNode", back_populates="inventory_items", foreign_keys=[network_node_id]
    )
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
# Topology (ADR-003 config-driven)
# ---------------------------------------------------------------------------

class NetworkNodeType(Base):
    """Per-company node kind (OLT, PON port, splitter, ONU, ...) — configuration,
    not code. `allowed_parent_keys` constrains tree shape per company convention."""
    __tablename__ = "network_node_type"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime(timezone=True), nullable=False, default=now_gt)
    key = Column(String, nullable=False)     # "olt", "pon_port", "splitter", "onu"
    name = Column(String, nullable=False)    # display label
    category = Column(Enum(DeviceCategory), nullable=True)  # optional catalog hint
    icon = Column(String, nullable=True)     # frontend icon key
    allowed_parent_keys = Column(JSON, nullable=True)  # ["olt"] for pon_port, etc.
    attribute_schema = Column(JSON, nullable=True)

    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("company.id", ondelete="CASCADE"), nullable=False, index=True
    )

    company = relationship("Company", back_populates="network_node_types")
    nodes = relationship("NetworkNode", back_populates="node_type")

    __table_args__ = (
        UniqueConstraint("company_id", "key", name="uq_network_node_type_company_key"),
    )


class NetworkNode(Base):
    """Topology instance node. Containment tree via parent_id
    (OLT -> PON port -> splitter -> ONU); non-tree overlays via NetworkLink."""
    __tablename__ = "network_node"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime(timezone=True), nullable=False, default=now_gt)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=now_gt, onupdate=now_gt)
    name = Column(String, nullable=False)
    status = Column(
        Enum(NetworkNodeStatus), nullable=False,
        default=NetworkNodeStatus.ACTIVE, server_default='ACTIVE'
    )
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    capacity = Column(Integer, nullable=True)  # e.g. splitter output count
    attributes = Column(JSON, nullable=True)
    notes = Column(String, nullable=True)

    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("company.id", ondelete="CASCADE"), nullable=False, index=True
    )
    node_type_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("network_node_type.id", ondelete="RESTRICT"), nullable=False
    )
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("network_node.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # The physical asset fulfilling this node (if serialized in inventory).
    inventory_item_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("inventory_item.id", ondelete="SET NULL"), nullable=True
    )

    company = relationship("Company", back_populates="network_nodes")
    node_type = relationship("NetworkNodeType", back_populates="nodes")
    parent = relationship("NetworkNode", remote_side=[id], backref="children")
    inventory_items = relationship(
        "InventoryItem", back_populates="network_node",
        foreign_keys="InventoryItem.network_node_id",
    )
    client_services = relationship("ClientService", back_populates="network_node")


class NetworkLink(Base):
    """Non-tree edge overlay (rings, redundancy, logical links)."""
    __tablename__ = "network_link"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime(timezone=True), nullable=False, default=now_gt)
    link_type = Column(String, nullable=False, default="fiber")  # fiber, wireless, logical
    attributes = Column(JSON, nullable=True)

    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("company.id", ondelete="CASCADE"), nullable=False, index=True
    )
    from_node_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("network_node.id", ondelete="CASCADE"), nullable=False
    )
    to_node_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("network_node.id", ondelete="CASCADE"), nullable=False
    )

    from_node = relationship("NetworkNode", foreign_keys=[from_node_id])
    to_node = relationship("NetworkNode", foreign_keys=[to_node_id])


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
    network_node_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("network_node.id", ondelete="SET NULL"), nullable=True
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
    network_node = relationship("NetworkNode")
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
