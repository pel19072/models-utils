# database_utils/dependencies/audit.py
"""
FastAPI dependencies for audit logging context.

This module provides dependencies to capture audit-related information
like user ID and IP address from requests, making it easy to add
comprehensive audit logging to any endpoint.
"""
from __future__ import annotations

import logging
from typing import Optional, TYPE_CHECKING
from fastapi import Request, Depends
from database_utils.dependencies.auth import get_current_user

if TYPE_CHECKING:
    from database_utils.models.auth import User

# Configure module logger
logger = logging.getLogger(__name__)


class AuditContext:
    """
    Container for audit logging context information.

    This class holds information about the current request that
    should be logged in audit trails.
    """

    def __init__(
        self,
        user_id: Optional[int],
        ip_address: Optional[str],
        user: Optional["User"] = None
    ):
        """
        Initialize audit context.

        Args:
            user_id: ID of the authenticated user (None for unauthenticated)
            ip_address: IP address of the client making the request
            user: Full user object (optional, for convenience)
        """
        self.user_id = user_id
        self.ip_address = ip_address
        self.user = user

    def __repr__(self) -> str:
        return f"AuditContext(user_id={self.user_id}, ip_address={self.ip_address})"


def get_client_ip(request: Request) -> Optional[str]:
    """
    Extract the client IP address from the request.

    Checks multiple headers in order of preference:
    1. X-Forwarded-For (for proxied requests)
    2. X-Real-IP (alternative proxy header)
    3. request.client.host (direct connection)

    Args:
        request: FastAPI Request object

    Returns:
        str: IP address of the client, or None if not available
    """
    # Try X-Forwarded-For header (most common for proxied requests)
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # X-Forwarded-For can contain multiple IPs (client, proxy1, proxy2, ...)
        # The first one is the original client
        ip = forwarded_for.split(",")[0].strip()
        logger.debug(f"IP from X-Forwarded-For: {ip}")
        return ip

    # Try X-Real-IP header
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        logger.debug(f"IP from X-Real-IP: {real_ip}")
        return real_ip

    # Fall back to direct client IP
    if request.client:
        ip = request.client.host
        logger.debug(f"IP from request.client: {ip}")
        return ip

    logger.warning("Could not determine client IP address")
    return None


async def get_audit_context(
    request: Request,
    user: "User" = Depends(get_current_user)
) -> AuditContext:
    """
    Dependency to get audit context for authenticated endpoints.

    Use this dependency in endpoints that require authentication
    and need audit logging.

    Args:
        request: FastAPI Request object (auto-injected)
        user: Authenticated user (auto-injected via dependency)

    Returns:
        AuditContext: Container with user_id, ip_address, and user object

    Example:
        @router.post("/clients")
        async def create_client(
            client_in: ClientCreate,
            db: Session = Depends(get_db),
            audit: AuditContext = Depends(get_audit_context)
        ):
            # Create client
            client = Client(**client_in.dict())
            db.add(client)
            db.commit()

            # Log the creation
            log_create_operation(
                db=db,
                user_id=audit.user_id,
                resource_type="client",
                resource_id=client.id,
                resource_data=client,
                ip_address=audit.ip_address
            )

            return client
    """
    ip_address = get_client_ip(request)

    logger.debug(
        f"Audit context created for user_id={user.id}, ip={ip_address}"
    )

    return AuditContext(
        user_id=user.id,
        ip_address=ip_address,
        user=user
    )


async def get_audit_context_optional(request: Request) -> AuditContext:
    """
    Dependency to get audit context for endpoints that may or may not
    require authentication.

    Use this for public endpoints where you still want to log actions
    but don't require authentication.

    Args:
        request: FastAPI Request object (auto-injected)

    Returns:
        AuditContext: Container with ip_address and user_id=None

    Example:
        @router.post("/public/signup")
        async def signup(
            user_in: UserCreate,
            db: Session = Depends(get_db),
            audit: AuditContext = Depends(get_audit_context_optional)
        ):
            # Create user
            user = User(**user_in.dict())
            db.add(user)
            db.commit()

            # Log the creation (user_id will be None since it's signup)
            log_custom_operation(
                db=db,
                user_id=audit.user_id,
                action="user.signup",
                resource_type="user",
                resource_id=user.id,
                ip_address=audit.ip_address
            )

            return user
    """
    ip_address = get_client_ip(request)

    logger.debug(f"Audit context created for unauthenticated request, ip={ip_address}")

    return AuditContext(
        user_id=None,
        ip_address=ip_address,
        user=None
    )
