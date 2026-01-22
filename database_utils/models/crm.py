from sqlalchemy import (
    Column, String, Integer, Boolean, JSON, DateTime, ForeignKey, Enum, text, Uuid
)
from sqlalchemy.orm import relationship, Mapped, mapped_column

from database_utils.database import Base

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


class Client(Base):
    __tablename__ = "client"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
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


class Product(Base):
    __tablename__ = "product"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    name = Column(String, nullable=False)
    price = Column(Integer, nullable=False)
    description = Column(String, nullable=False)
    stock = Column(Integer, nullable=False)

    company_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("company.id", ondelete="CASCADE"), nullable=False)

    # Relationships
    company = relationship("Company", back_populates="products")
    order_items = relationship("OrderItem", back_populates="product", cascade="all, delete-orphan")


class RecurringOrder(Base):
    __tablename__ = "recurring_order"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    recurrence = Column(Enum(RecurrenceEnum), nullable=False)
    recurrence_end = Column(DateTime, nullable=True)
    last_generated_at = Column(DateTime, nullable=True)
    next_generation_date = Column(DateTime, nullable=True)
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
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    recurring_order_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("recurring_order.id", ondelete="CASCADE"))
    product_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("product.id", ondelete="CASCADE"))
    quantity = Column(Integer, nullable=False)

    # Relationships
    recurring_order = relationship("RecurringOrder", back_populates="template_items")
    product = relationship("Product")


class Order(Base):
    __tablename__ = "order"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    date = Column(DateTime, nullable=False)
    total = Column(Integer, nullable=False)
    paid = Column(Boolean, nullable=False)
    generation_date = Column(DateTime, nullable=True)  # The period/date this recurring order was generated for

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
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    order_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("order.id", ondelete="CASCADE"), nullable=False)
    product_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("product.id", ondelete="CASCADE"), nullable=False)
    quantity = Column(Integer, nullable=False)

    # Relationships
    order = relationship("Order", back_populates="order_items")
    product = relationship("Product", back_populates="order_items")


class Invoice(Base):
    __tablename__ = "invoice"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    issue_date = Column(DateTime, nullable=False)
    subtotal = Column(Integer, nullable=False)
    tax = Column(Integer, nullable=False)
    total = Column(Integer, nullable=False)
    details = Column(JSON, nullable=False)

    company_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("company.id", ondelete="CASCADE"), nullable=False)
    order_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("order.id", ondelete="CASCADE"), nullable=False)

    # Relationships
    company = relationship("Company", back_populates="invoices")
    order = relationship("Order", back_populates="invoices")


class CustomField(Base):
    __tablename__ = "custom_field"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    table = Column(String, nullable=False)
    field_name = Column(String, nullable=False)
    field_type = Column(String, nullable=False)
    field_value = Column(String, nullable=True)

    company_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("company.id", ondelete="CASCADE"), nullable=False)

    # Relationships
    company = relationship("Company", back_populates="custom_fields")