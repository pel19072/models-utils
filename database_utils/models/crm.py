from sqlalchemy import (
    Column, String, Integer, Boolean, JSON, DateTime, ForeignKey
)
from sqlalchemy.orm import relationship

from database_utils.database import Base

from datetime import datetime

class Client(Base):
    __tablename__ = "client"

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    name = Column(String, nullable=False)
    tax_id = Column(String, nullable=True)
    address = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    email = Column(String, nullable=True)
    contact = Column(String, nullable=True)
    observations = Column(String, nullable=True)

    company_id = Column(Integer, ForeignKey("company.id", ondelete="CASCADE"), nullable=False)
    advisor_id = Column(Integer, ForeignKey("user.id", ondelete="SET NULL"), nullable=True)

    # Relationships
    company = relationship("Company", back_populates="clients")
    advisor = relationship("User", back_populates="clients")
    orders = relationship("Order", back_populates="client", cascade="all, delete-orphan")

class Product(Base):
    __tablename__ = "product"

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    name = Column(String, nullable=False)
    price = Column(Integer, nullable=False)
    description = Column(String, nullable=False)
    stock = Column(Integer, nullable=False)

    company_id = Column(Integer, ForeignKey("company.id", ondelete="CASCADE"), nullable=False)

    # Relationships
    company = relationship("Company", back_populates="products")
    order_items = relationship("OrderItem", back_populates="product", cascade="all, delete-orphan")

class Order(Base):
    __tablename__ = "order"

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    date = Column(DateTime, nullable=False)
    total = Column(Integer, nullable=False)
    paid = Column(Boolean, nullable=False)
    recurring = Column(Boolean, nullable=False)
    recurrence = Column(String, nullable=True)

    company_id = Column(Integer, ForeignKey("company.id", ondelete="CASCADE"), nullable=False)
    client_id = Column(Integer, ForeignKey("client.id", ondelete="SET NULL"), nullable=True)

    # Relationships
    company = relationship("Company", back_populates="orders")
    client = relationship("Client", back_populates="orders")
    invoices = relationship("Invoice", back_populates="order", cascade="all, delete-orphan")
    order_items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")

class OrderItem(Base):
    __tablename__ = "order_item"

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    order_id = Column(Integer, ForeignKey("order.id", ondelete="CASCADE"), nullable=False)
    product_id = Column(Integer, ForeignKey("product.id", ondelete="CASCADE"), nullable=False)
    quantity = Column(Integer, nullable=False)

    # Relationships
    order = relationship("Order", back_populates="order_items")
    product = relationship("Product", back_populates="order_items")

class Invoice(Base):
    __tablename__ = "invoice"

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    issue_date = Column(DateTime, nullable=False)
    subtotal = Column(Integer, nullable=False)
    tax = Column(Integer, nullable=False)
    total = Column(Integer, nullable=False)
    details = Column(JSON, nullable=False)

    company_id = Column(Integer, ForeignKey("company.id", ondelete="CASCADE"), nullable=False)
    order_id = Column(Integer, ForeignKey("order.id", ondelete="CASCADE"), nullable=False)

    # Relationships
    company = relationship("Company", back_populates="invoices")
    order = relationship("Order", back_populates="invoices")

class CustomField(Base):
    __tablename__ = "custom_field"

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    table = Column(String, nullable=False)
    field_name = Column(String, nullable=False)
    field_type = Column(String, nullable=False)
    field_value = Column(String, nullable=True)

    company_id = Column(Integer, ForeignKey("company.id", ondelete="CASCADE"), nullable=False)

    # Relationships
    company = relationship("Company", back_populates="custom_fields")
    