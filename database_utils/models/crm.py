from sqlalchemy import (
    Column, String, Integer, Boolean, JSON, DateTime, ForeignKey, Enum, text, Uuid, Float
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


class CustomFieldType(str, enum.Enum):
    TEXT = "TEXT"
    NUMBER = "NUMBER"
    EMAIL = "EMAIL"
    PHONE = "PHONE"
    URL = "URL"
    DATE = "DATE"
    BOOLEAN = "BOOLEAN"


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

    company_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("company.id", ondelete="CASCADE"), nullable=False)
    advisor_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("user.id", ondelete="SET NULL"), nullable=True)

    # Relationships
    company = relationship("Company", back_populates="clients")
    advisor = relationship("User", back_populates="clients")
    orders = relationship("Order", back_populates="client", cascade="all, delete-orphan")
    recurring_orders = relationship("RecurringOrder", back_populates="client", cascade="all, delete-orphan")
    custom_field_values = relationship("ClientCustomFieldValue", back_populates="client", cascade="all, delete-orphan")


class Product(Base):
    __tablename__ = "product"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime(timezone=True), nullable=False, default=now_gt)
    name = Column(String, nullable=False)
    price = Column(Float, nullable=False)
    description = Column(String, nullable=False)
    stock = Column(Integer, nullable=False)

    company_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("company.id", ondelete="CASCADE"), nullable=False)

    # Relationships
    company = relationship("Company", back_populates="products")
    order_items = relationship("OrderItem", back_populates="product", cascade="all, delete-orphan")


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
    company_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("company.id", ondelete="CASCADE"), nullable=False)

    # Relationships
    client = relationship("Client", back_populates="recurring_orders")
    company = relationship("Company", back_populates="recurring_orders")
    template_items = relationship("RecurringOrderItem", back_populates="recurring_order", cascade="all, delete-orphan")
    generated_orders = relationship("Order", back_populates="recurring_order")


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
    paid = Column(Boolean, nullable=False)
    status = Column(Enum(OrderStatus), nullable=False, default=OrderStatus.ACTIVE, server_default='ACTIVE')

    company_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("company.id", ondelete="CASCADE"), nullable=False)
    client_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("client.id", ondelete="SET NULL"), nullable=True)
    recurring_order_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("recurring_order.id", ondelete="SET NULL"), nullable=True)

    # Relationships
    company = relationship("Company", back_populates="orders")
    client = relationship("Client", back_populates="orders")
    invoices = relationship("Invoice", back_populates="order", cascade="all, delete-orphan")
    order_items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    recurring_order = relationship("RecurringOrder", back_populates="generated_orders")


class OrderItem(Base):
    __tablename__ = "order_item"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime(timezone=True), nullable=False, default=now_gt)
    order_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("order.id", ondelete="CASCADE"), nullable=False)
    product_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("product.id", ondelete="CASCADE"), nullable=False)
    quantity = Column(Integer, nullable=False)

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
    details = Column(JSON, nullable=False)
    is_valid = Column(Boolean, nullable=False, default=True)

    company_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("company.id", ondelete="CASCADE"), nullable=False)
    order_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("order.id", ondelete="CASCADE"), nullable=False)

    # Relationships
    company = relationship("Company", back_populates="invoices")
    order = relationship("Order", back_populates="invoices")


class CustomFieldDefinition(Base):
    __tablename__ = "custom_field_definition"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime(timezone=True), nullable=False, default=now_gt)

    field_name = Column(String, nullable=False)  # The human-readable label
    field_key = Column(String, nullable=False)  # The unique identifier (e.g., "ip_address")
    field_type = Column(Enum(CustomFieldType), nullable=False)
    is_required = Column(Boolean, nullable=False, default=False)
    display_order = Column(Integer, nullable=False, default=0)

    company_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("company.id", ondelete="CASCADE"), nullable=False)

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