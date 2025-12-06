from sqlalchemy import (
    Column, String, Integer, Boolean, DateTime, ForeignKey, Table, Text, JSON
)
from sqlalchemy.orm import relationship

from database_utils.database import Base

from datetime import datetime

# Association table for many-to-many relationship between Role and Permission
role_permission = Table(
    'role_permission',
    Base.metadata,
    Column('role_id', Integer, ForeignKey('role.id', ondelete='CASCADE'), primary_key=True),
    Column('permission_id', Integer, ForeignKey('permission.id', ondelete='CASCADE'), primary_key=True)
)

# Association table for many-to-many relationship between User and Role
user_role = Table(
    'user_role',
    Base.metadata,
    Column('user_id', Integer, ForeignKey('user.id', ondelete='CASCADE'), primary_key=True),
    Column('role_id', Integer, ForeignKey('role.id', ondelete='CASCADE'), primary_key=True)
)

class Tier(Base):
    __tablename__ = "tier"

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    name = Column(String, nullable=False, unique=True)
    companies = relationship("Company", back_populates="tier")


class Company(Base):
    __tablename__ = "company"

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    name = Column(String, nullable=False, unique=True)
    email = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    active = Column(Boolean, default=True)
    start_date = Column(DateTime, nullable=True)
    tier_id = Column(Integer, ForeignKey("tier.id"), nullable=False)
    tax_id = Column(String, nullable=True)
    address = Column(String, nullable=True)

    # Relationships
    tier = relationship("Tier", back_populates="companies")
    users = relationship("User", back_populates="company", cascade="all, delete-orphan")
    clients = relationship("Client", back_populates="company", cascade="all, delete-orphan")
    products = relationship("Product", back_populates="company", cascade="all, delete-orphan")
    orders = relationship("Order", back_populates="company", cascade="all, delete-orphan")
    invoices = relationship("Invoice", back_populates="company", cascade="all, delete-orphan")
    custom_fields = relationship("CustomField", back_populates="company", cascade="all, delete-orphan")
    notifications = relationship("Notification", back_populates="company", cascade="all, delete-orphan")
    recurring_orders = relationship("RecurringOrder", back_populates="company", cascade="all, delete-orphan")


class Permission(Base):
    __tablename__ = "permission"

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    name = Column(String, nullable=False, unique=True)  # e.g., "clients.read", "orders.create"
    resource = Column(String, nullable=False)  # e.g., "clients", "orders", "products"
    action = Column(String, nullable=False)  # e.g., "create", "read", "update", "delete"
    description = Column(Text, nullable=True)

    # Relationships
    roles = relationship("Role", secondary=role_permission, back_populates="permissions")


class Role(Base):
    __tablename__ = "role"

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    name = Column(String, nullable=False, unique=True)  # e.g., "ADMIN", "MANAGER", "SALES"
    description = Column(Text, nullable=True)
    is_system = Column(Boolean, default=False)  # System roles (ADMIN, USER) cannot be deleted

    # Relationships
    permissions = relationship("Permission", secondary=role_permission, back_populates="roles")
    users = relationship("User", secondary=user_role, back_populates="roles")


class User(Base):
    __tablename__ = "user"

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    name = Column(String, nullable=False)
    email = Column(String, nullable=False, unique=True)
    age = Column(Integer, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, default="USER")  # Legacy field - kept for backward compatibility
    admin = Column(Boolean, default=False)  # Legacy field - kept for backward compatibility

    company_id = Column(Integer, ForeignKey("company.id", ondelete="CASCADE"), nullable=True)
    is_super_admin = Column(Boolean, default=False, nullable=False)

    # Relationships
    company = relationship("Company", back_populates="users")
    clients = relationship("Client", back_populates="advisor", cascade="all, delete-orphan")
    notifications = relationship("Notification", back_populates="user", cascade="all, delete-orphan")
    roles = relationship("Role", secondary=user_role, back_populates="users")


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


class AuditLog(Base):
    """Audit log for tracking super admin actions"""
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    user_id = Column(Integer, ForeignKey("user.id", ondelete="SET NULL"), nullable=True)
    action = Column(String, nullable=False)  # e.g., "company.disable", "tier.create"
    resource_type = Column(String, nullable=False)  # e.g., "company", "tier", "user"
    resource_id = Column(Integer, nullable=True)
    details = Column(JSON, nullable=True)  # Store before/after state, additional context
    ip_address = Column(String, nullable=True)

    # Relationships
    user = relationship("User")
