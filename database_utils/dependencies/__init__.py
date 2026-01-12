# database_utils/dependencies/__init__.py
"""
FastAPI dependencies for authentication, authorization, and database access.

This module provides reusable dependency functions that can be injected
into FastAPI route handlers using the Depends() function.
"""

from database_utils.dependencies.db import get_db
from database_utils.dependencies.auth import (
    get_token_from_header,
    get_current_user,
    get_admin_user,
    get_super_admin,
    get_company_id,
    require_roles
)
from database_utils.dependencies.audit import (
    AuditContext,
    get_client_ip,
    get_audit_context,
    get_audit_context_optional
)

__all__ = [
    "get_db",
    "get_token_from_header",
    "get_current_user",
    "get_admin_user",
    "get_super_admin",
    "get_company_id",
    "require_roles",
    "AuditContext",
    "get_client_ip",
    "get_audit_context",
    "get_audit_context_optional"
]
