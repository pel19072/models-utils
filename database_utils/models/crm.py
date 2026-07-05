from sqlalchemy import (
    Column, String, Integer, BigInteger, Boolean, JSON, DateTime, ForeignKey, Enum, text, Uuid, Float,
    Table, Index, CheckConstraint
)
from sqlalchemy.orm import relationship, Mapped, mapped_column

from database_utils.database import Base
from ..utils.timezone_utils import now_gt

from datetime import datetime
import enum
import uuid

class RecurrenceEnum(str, enum.Enum):
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"
    YEARLY = "YEARLY"


class RecurringOrderStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    INACTIVE = "INACTIVE"
    CANCELLED = "CANCELLED"


class OrderStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    CANCELLED = "CANCELLED"


class PaymentStatus(str, enum.Enum):
    """Stored payment state of an order. OVERDUE is never stored — it is
    computed (payment_status IN (PENDING, PARTIAL) AND due_date < today
    AND status = 'ACTIVE') and serialized as `is_overdue` on OrderOut."""
    PENDING = "PENDING"
    PARTIAL = "PARTIAL"
    PAID = "PAID"
    REFUNDED = "REFUNDED"


class OrderType(str, enum.Enum):
    RECURRING = "RECURRING"
    ONE_SHOT = "ONE_SHOT"
    INSTALLATION = "INSTALLATION"


class PaymentKind(str, enum.Enum):
    """Direction of a ledger row. amount_cents is always positive (unsigned);
    direction comes from the kind, never from the sign."""
    PAYMENT = "PAYMENT"
    REFUND = "REFUND"


class PaymentMethodType(str, enum.Enum):
    """Name avoids colliding with the existing PaymentMethod model (auth.py).
    LEGACY is used only by the migration backfill (reference='LEGACY_BACKFILL');
    the UI renders it as "Pago migrado / Migrated payment"."""
    CASH = "CASH"
    TRANSFER = "TRANSFER"
    CARD = "CARD"
    DEPOSIT = "DEPOSIT"
    OTHER = "OTHER"
    LEGACY = "LEGACY"


class CustomFieldType(str, enum.Enum):
    TEXT = "TEXT"
    NUMBER = "NUMBER"
    EMAIL = "EMAIL"
    PHONE = "PHONE"
    URL = "URL"
    DATE = "DATE"
    BOOLEAN = "BOOLEAN"


class TaskStateColor(str, enum.Enum):
    GRAY = "GRAY"
    RED = "RED"
    ORANGE = "ORANGE"
    YELLOW = "YELLOW"
    GREEN = "GREEN"
    BLUE = "BLUE"
    PURPLE = "PURPLE"
    PINK = "PINK"


class TaskLinkedObjectType(str, enum.Enum):
    CLIENT = "CLIENT"
    ORDER = "ORDER"
    RECURRING_ORDER = "RECURRING_ORDER"
    CLIENT_SERVICE = "CLIENT_SERVICE"
    INVENTORY_ITEM = "INVENTORY_ITEM"
    NETWORK_NODE = "NETWORK_NODE"


class ServiceAvailability(str, enum.Enum):
    UNKNOWN = "UNKNOWN"
    SERVICEABLE = "SERVICEABLE"
    NOT_SERVICEABLE = "NOT_SERVICEABLE"
    SURVEY_REQUIRED = "SURVEY_REQUIRED"


class InstallationStatus(str, enum.Enum):
    NOT_INSTALLED = "NOT_INSTALLED"
    SURVEY_SCHEDULED = "SURVEY_SCHEDULED"
    INSTALL_SCHEDULED = "INSTALL_SCHEDULED"
    INSTALLED = "INSTALLED"
    CANCELLED = "CANCELLED"


# Association table for many-to-many relationship between Task and User (assignees)
task_assignee = Table(
    'task_assignee',
    Base.metadata,
    Column('task_id', Uuid, ForeignKey('task.id', ondelete='CASCADE'), primary_key=True),
    Column('user_id', Uuid, ForeignKey('user.id', ondelete='CASCADE'), primary_key=True)
)


class Client(Base):
    __tablename__ = "client"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime(timezone=True), nullable=False, default=now_gt)
    name = Column(String, nullable=False)
    tax_id = Column(String, nullable=True)
    address = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    email = Column(String, nullable=True)
    contact = Column(String, nullable=True)
    observations = Column(String, nullable=True)

    # ISP fields (ADR-004): queried subscriber data promoted to columns.
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    gps_precision_m = Column(Float, nullable=True)
    installation_address = Column(String, nullable=True)  # distinct from billing address
    service_availability = Column(
        Enum(ServiceAvailability), nullable=False,
        default=ServiceAvailability.UNKNOWN, server_default='UNKNOWN'
    )
    installation_status = Column(
        Enum(InstallationStatus), nullable=False,
        default=InstallationStatus.NOT_INSTALLED, server_default='NOT_INSTALLED'
    )
    installation_date = Column(DateTime(timezone=True), nullable=True)

    company_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("company.id", ondelete="CASCADE"), nullable=False, index=True)
    advisor_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("user.id", ondelete="SET NULL"), nullable=True)
    assigned_technician_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("user.id", ondelete="SET NULL"), nullable=True)

    # Relationships
    company = relationship("Company", back_populates="clients")
    advisor = relationship("User", back_populates="clients", foreign_keys=[advisor_id])
    assigned_technician = relationship("User", foreign_keys=[assigned_technician_id])
    services = relationship("ClientService", back_populates="client", cascade="all, delete-orphan")
    equipment = relationship("InventoryItem", back_populates="client")
    # DATA-1: NO delete-orphan cascade on orders/recurring_orders. The FK is
    # ondelete=SET NULL by design (an order/recurring order outlives its client),
    # and delete_client blocks deletion while orders exist. A delete-orphan cascade
    # here would silently destroy a client's entire order + invoice history.
    orders = relationship("Order", back_populates="client")
    recurring_orders = relationship("RecurringOrder", back_populates="client")
    custom_field_values = relationship("ClientCustomFieldValue", back_populates="client", cascade="all, delete-orphan")


class Product(Base):
    __tablename__ = "product"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime(timezone=True), nullable=False, default=now_gt)
    name = Column(String, nullable=False)
    price = Column(Float, nullable=False)
    # Money-in-cents shadow column (Cycle 1 dual-write; Float `price` drops in
    # Cycle 2). Nullable, no server_default — see doc 16 §1.
    price_cents = Column(BigInteger, nullable=True)
    description = Column(String, nullable=False)
    stock = Column(Integer, nullable=False)

    company_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("company.id", ondelete="CASCADE"), nullable=False, index=True)

    # Relationships
    company = relationship("Company", back_populates="products")
    # NO delete-orphan cascade (doc 16 §2.2, MAJOR fix): deleting a Product must
    # never destroy billed history. order_item.product_id is ondelete=SET NULL;
    # the item survives with its unit_price_cents/product_name snapshot.
    order_items = relationship("OrderItem", back_populates="product")


class RecurringOrder(Base):
    __tablename__ = "recurring_order"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime(timezone=True), default=now_gt, nullable=False)
    recurrence = Column(Enum(RecurrenceEnum), nullable=False)
    recurrence_end = Column(DateTime(timezone=True), nullable=True)
    last_generated_at = Column(DateTime(timezone=True), nullable=True)
    next_generation_date = Column(DateTime(timezone=True), nullable=True)
    status = Column(Enum(RecurringOrderStatus), nullable=False, default=RecurringOrderStatus.ACTIVE, server_default='ACTIVE')

    client_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("client.id", ondelete="SET NULL"), nullable=True)
    company_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("company.id", ondelete="CASCADE"), nullable=False, index=True)

    # Relationships
    client = relationship("Client", back_populates="recurring_orders")
    company = relationship("Company", back_populates="recurring_orders")
    template_items = relationship("RecurringOrderItem", back_populates="recurring_order", cascade="all, delete-orphan")
    generated_orders = relationship("Order", back_populates="recurring_order")

    # PERF-1: the cron "due recurring orders" scan filters by status (+ company_id).
    __table_args__ = (
        Index("ix_recurring_order_status_company", "status", "company_id"),
    )


class RecurringOrderItem(Base):
    __tablename__ = "recurring_order_item"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime(timezone=True), default=now_gt, nullable=False)

    recurring_order_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("recurring_order.id", ondelete="CASCADE"))
    product_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("product.id", ondelete="CASCADE"))
    quantity = Column(Integer, nullable=False)

    # Relationships
    recurring_order = relationship("RecurringOrder", back_populates="template_items")
    product = relationship("Product")


class Order(Base):
    __tablename__ = "order"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime(timezone=True), nullable=False, default=now_gt)
    due_date = Column(DateTime(timezone=True), nullable=True)  # When the order is due (optional for regular orders, calculated for recurring)
    payment_date = Column(DateTime(timezone=True), nullable=True)  # When the order was paid (automatically set when paid=True)
    total = Column(Float, nullable=False)
    # Money-in-cents (Cycle 1 dual-write; Float `total` drops in Cycle 2).
    # Nullable, NO server_default (doc 16 §1 — a default would silently corrupt
    # revenue and defeat the IS NULL backfill guards). NOT NULL arrives in R4.
    total_cents = Column(BigInteger, nullable=True)
    paid = Column(Boolean, nullable=False)
    status = Column(Enum(OrderStatus), nullable=False, default=OrderStatus.ACTIVE, server_default='ACTIVE')
    order_type = Column(Enum(OrderType), nullable=False, default=OrderType.ONE_SHOT, server_default='ONE_SHOT')
    # Single writer: backend-erp services/payment_service.py. Nothing else ever
    # writes paid / payment_status / payment_date (workflow engine denylist).
    payment_status = Column(
        Enum(PaymentStatus), nullable=False,
        default=PaymentStatus.PENDING, server_default='PENDING'
    )

    company_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("company.id", ondelete="CASCADE"), nullable=False, index=True)
    client_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("client.id", ondelete="SET NULL"), nullable=True)
    recurring_order_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("recurring_order.id", ondelete="SET NULL"), nullable=True)
    client_service_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("client_service.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # Relationships
    company = relationship("Company", back_populates="orders")
    client = relationship("Client", back_populates="orders")
    invoices = relationship("Invoice", back_populates="order", cascade="all, delete-orphan")
    order_items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    recurring_order = relationship("RecurringOrder", back_populates="generated_orders")
    # Append-only ledger — NO delete-orphan cascade, ever (doc 16 §2.2). The
    # payment.order_id FK is ondelete=RESTRICT: the DB refuses to delete an
    # order that has money history.
    payments = relationship("Payment", back_populates="order")

    # Partial unique index: at most one non-cancelled order per (recurring_order_id, due_date).
    # Prevents the duplicate-generation race in RecurringOrderService.generate_order_from_template.
    __table_args__ = (
        Index(
            "uq_order_active_recurring_due_date",
            "recurring_order_id",
            "due_date",
            unique=True,
            postgresql_where=text("status != 'CANCELLED' AND recurring_order_id IS NOT NULL"),
        ),
        # PERF-1: serves the hot "overdue / delayed-unpaid" dashboard query
        # (company_id + paid=false + status=ACTIVE + due_date).
        Index(
            "ix_order_company_overdue",
            "company_id",
            "due_date",
            postgresql_where=text("paid = false AND status = 'ACTIVE'"),
        ),
    )


class OrderItem(Base):
    __tablename__ = "order_item"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime(timezone=True), nullable=False, default=now_gt)
    order_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("order.id", ondelete="CASCADE"), nullable=False)
    # SET NULL (doc 16 §2.2): deleting a Product must never destroy billed
    # history — the snapshot columns below keep the line meaningful.
    product_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("product.id", ondelete="SET NULL"), nullable=True)
    quantity = Column(Integer, nullable=False)
    # Price/name snapshots at order time. Nullable so "missing snapshot"
    # (pre-backfill history) is distinguishable from "free item"; app-level
    # required for all new rows.
    unit_price_cents = Column(BigInteger, nullable=True)
    product_name = Column(String, nullable=True)

    # Relationships
    order = relationship("Order", back_populates="order_items")
    product = relationship("Product", back_populates="order_items")


class Invoice(Base):
    __tablename__ = "invoice"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime(timezone=True), nullable=False, default=now_gt)
    issue_date = Column(DateTime(timezone=True), nullable=False)
    subtotal = Column(Float, nullable=False)
    tax = Column(Float, nullable=False)
    total = Column(Float, nullable=False)
    # Money-in-cents shadow columns (Cycle 1 dual-write; Floats drop in Cycle 2).
    # Nullable, no server_default; NOT NULL arrives in R4. Identity invariant:
    # subtotal_cents + tax_cents == total_cents (backfill derives subtotal).
    subtotal_cents = Column(BigInteger, nullable=True)
    tax_cents = Column(BigInteger, nullable=True)
    total_cents = Column(BigInteger, nullable=True)
    details = Column(JSON, nullable=False)
    is_valid = Column(Boolean, nullable=False, default=True)

    company_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("company.id", ondelete="CASCADE"), nullable=False, index=True)
    # NOTE (doc 16 §2.2): CASCADE -> RESTRICT and removal of Order.invoices
    # delete-orphan cascade are deferred to R4 (the app delete guard covers the
    # window).
    order_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("order.id", ondelete="CASCADE"), nullable=False)

    # Relationships
    company = relationship("Company", back_populates="invoices")
    order = relationship("Order", back_populates="invoices")

    __table_args__ = (
        # At most one valid invoice per order. Created in revision R3
        # (c1c_payment_ledger), after R2 remediates any historical duplicates.
        Index(
            "uq_invoice_order_valid",
            "order_id",
            unique=True,
            postgresql_where=text("is_valid"),
        ),
    )


class Payment(Base):
    """Append-only tenant-money ledger. Never UPDATE/DELETE; corrections are
    REFUND rows (reverses_payment_id -> the original PAYMENT). Doc 16 §2.1."""
    __tablename__ = "payment"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime(timezone=True), nullable=False, default=now_gt)

    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("company.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # RESTRICT: DB-level guard — an order with money history cannot be deleted.
    order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("order.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    # Stamped on the settling payment (the one that transitions the order to PAID).
    invoice_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("invoice.id", ondelete="SET NULL"), nullable=True
    )
    kind = Column(Enum(PaymentKind), nullable=False)
    amount_cents = Column(BigInteger, nullable=False)  # always positive (CHECK)
    method = Column(
        Enum(PaymentMethodType), nullable=False,
        default=PaymentMethodType.OTHER, server_default='OTHER'
    )
    reference = Column(String, nullable=True)  # receipt / transfer id / 'LEGACY_BACKFILL'
    paid_at = Column(DateTime(timezone=True), nullable=False, default=now_gt)
    received_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("user.id", ondelete="SET NULL"), nullable=True
    )
    # REFUND -> original PAYMENT. RESTRICT: a refunded payment cannot vanish.
    reverses_payment_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("payment.id", ondelete="RESTRICT"), nullable=True
    )
    notes = Column(String, nullable=True)

    # Relationships
    order = relationship("Order", back_populates="payments")
    invoice = relationship("Invoice")
    receiver = relationship("User", foreign_keys=[received_by])
    reverses_payment = relationship("Payment", remote_side=[id])

    __table_args__ = (
        CheckConstraint("amount_cents > 0", name="ck_payment_amount_positive"),
        CheckConstraint(
            "(kind = 'PAYMENT') = (reverses_payment_id IS NULL)",
            name="ck_payment_refund_link",
        ),
        Index("ix_payment_company_order", "company_id", "order_id"),
        Index("ix_payment_company_paid_at", "company_id", "paid_at"),
    )


class CustomFieldDefinition(Base):
    __tablename__ = "custom_field_definition"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime(timezone=True), nullable=False, default=now_gt)

    field_name = Column(String, nullable=False)  # The human-readable label
    field_key = Column(String, nullable=False)  # The unique identifier (e.g., "ip_address")
    field_type = Column(Enum(CustomFieldType), nullable=False)
    is_required = Column(Boolean, nullable=False, default=False)
    display_order = Column(Integer, nullable=False, default=0)

    company_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("company.id", ondelete="CASCADE"), nullable=False, index=True)

    # Relationships
    company = relationship("Company", back_populates="custom_field_definitions")
    client_values = relationship("ClientCustomFieldValue", back_populates="field_definition", cascade="all, delete-orphan")


class ClientCustomFieldValue(Base):
    __tablename__ = "client_custom_field_value"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime(timezone=True), nullable=False, default=now_gt)

    value = Column(String, nullable=True)  # All types stored as string

    client_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("client.id", ondelete="CASCADE"), nullable=False)
    field_definition_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("custom_field_definition.id", ondelete="CASCADE"), nullable=False)

    # Relationships
    client = relationship("Client", back_populates="custom_field_values")
    field_definition = relationship("CustomFieldDefinition", back_populates="client_values")


class TaskState(Base):
    __tablename__ = "task_state"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime(timezone=True), nullable=False, default=now_gt)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=now_gt, onupdate=now_gt)
    name = Column(String, nullable=False)
    color = Column(Enum(TaskStateColor), nullable=False, default=TaskStateColor.GRAY, server_default='GRAY')
    position = Column(Integer, nullable=False, default=0)

    company_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("company.id", ondelete="CASCADE"), nullable=False, index=True)

    # Relationships
    company = relationship("Company", back_populates="task_states")
    tasks = relationship("Task", back_populates="task_state", cascade="all, delete-orphan")


class Task(Base):
    __tablename__ = "task"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime(timezone=True), nullable=False, default=now_gt)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=now_gt, onupdate=now_gt)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    position = Column(Integer, nullable=False, default=0)
    due_date = Column(DateTime(timezone=True), nullable=True)
    time_spent_minutes = Column(Integer, nullable=True)
    linked_object_type = Column(Enum(TaskLinkedObjectType), nullable=True)
    linked_object_id = Column(Uuid, nullable=True)

    company_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("company.id", ondelete="CASCADE"), nullable=False, index=True)
    task_state_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("task_state.id", ondelete="RESTRICT"), nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("user.id", ondelete="SET NULL"), nullable=True)

    # Relationships
    company = relationship("Company", back_populates="tasks")
    task_state = relationship("TaskState", back_populates="tasks")
    creator = relationship("User", foreign_keys=[created_by])
    assignees = relationship("User", secondary=task_assignee)


class TaskTemplate(Base):
    __tablename__ = "task_template"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime(timezone=True), nullable=False, default=now_gt)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=now_gt, onupdate=now_gt)
    name = Column(String, nullable=False)
    task_name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    due_date_offset_days = Column(Integer, nullable=True)
    default_assignee_ids = Column(JSON, nullable=True)
    linked_object_type = Column(Enum(TaskLinkedObjectType), nullable=True)

    company_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("company.id", ondelete="CASCADE"), nullable=False, index=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("user.id", ondelete="SET NULL"), nullable=True)

    # Relationships
    company = relationship("Company", back_populates="task_templates")
    creator = relationship("User", foreign_keys=[created_by])


class IntegrationAuthType(str, enum.Enum):
    NONE = "NONE"
    API_KEY = "API_KEY"
    BEARER_TOKEN = "BEARER_TOKEN"
    BASIC_AUTH = "BASIC_AUTH"


class Integration(Base):
    __tablename__ = "integration"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime(timezone=True), nullable=False, default=now_gt)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=now_gt, onupdate=now_gt)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    base_url = Column(String, nullable=False)
    auth_type = Column(Enum(IntegrationAuthType), nullable=False, default=IntegrationAuthType.NONE)
    credentials = Column(JSON, nullable=True)
    # Credentials format per auth_type:
    # API_KEY:       {"header_name": "X-API-Key", "api_key": "sk-..."}
    # BEARER_TOKEN:  {"token": "eyJ..."}
    # BASIC_AUTH:    {"username": "admin", "password": "..."}

    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("company.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Relationships
    company = relationship("Company", back_populates="integrations")