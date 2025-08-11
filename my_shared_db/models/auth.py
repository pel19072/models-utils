from sqlalchemy import (
    Column, String, Integer, Boolean, DateTime, ForeignKey
)
from sqlalchemy.orm import relationship

from my_shared_db.database import Base

from datetime import datetime

class Company(Base):
    __tablename__ = "company"

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    name = Column(String, nullable=False, unique=True)
    email = Column(String, nullable=True)
    active = Column(Boolean, default=True)
    start_date = Column(DateTime, nullable=True)
    plan_id = Column(String(50), nullable=True)
    tax_id = Column(String, nullable=True)
    address = Column(String, nullable=True)

    # Relationships
    users = relationship("User", back_populates="company", cascade="all, delete-orphan")
    clients = relationship("Client", back_populates="company", cascade="all, delete-orphan")
    products = relationship("Product", back_populates="company", cascade="all, delete-orphan")
    orders = relationship("Order", back_populates="company", cascade="all, delete-orphan")
    invoices = relationship("Invoice", back_populates="company", cascade="all, delete-orphan")
    custom_fields = relationship("CustomField", back_populates="company", cascade="all, delete-orphan")
    notifications = relationship("Notification", back_populates="company", cascade="all, delete-orphan")

class User(Base):
    __tablename__ = "user"

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    name = Column(String, nullable=False)
    email = Column(String, nullable=False, unique=True)
    age = Column(Integer, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, default="USER")
    admin = Column(Boolean, default=False)

    company_id = Column(Integer, ForeignKey("company.id", ondelete="CASCADE"), nullable=False)

    # Relationships
    company = relationship("Company", back_populates="users")
    clients = relationship("Client", back_populates="advisor", cascade="all, delete-orphan")
    notifications = relationship("Notification", back_populates="user", cascade="all, delete-orphan")

class Notification(Base):
    __tablename__ = "notification"

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    status = Column(String, nullable=False, default="PENDING")  # PENDING, ACCEPTED, REJECTED

    # --- [INIT] Possible User data: Add User Fields ---
    name = Column(String, nullable=False)
    email = Column(String, nullable=False, unique=True)
    age = Column(Integer, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, default="USER")
    admin = Column(Boolean, default=False)
    # --- [END] Possible User data: Add User Fields ---

    company_id = Column(Integer, ForeignKey("company.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("user.id", ondelete="CASCADE"), nullable=True)

    # Relationships
    user = relationship("User", back_populates="notifications")
    company = relationship("Company", back_populates="notifications")
    