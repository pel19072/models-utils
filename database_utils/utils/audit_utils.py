# utils/audit_utils.py
from typing import Optional, Any
from sqlalchemy.ext.asyncio import AsyncSession
from database_utils.models.auth import AuditLog
from loguru import logger


async def create_audit_log(
    db: AsyncSession,
    user_id: Optional[int],
    action: str,
    resource_type: str,
    resource_id: Optional[int] = None,
    details: Optional[dict[str, Any]] = None,
    ip_address: Optional[str] = None
) -> AuditLog:
    """
    Create an audit log entry for super admin actions.

    Args:
        db: Database session
        user_id: ID of the user performing the action
        action: Action being performed (e.g., "company.disable", "tier.create")
        resource_type: Type of resource (e.g., "company", "tier", "user")
        resource_id: ID of the affected resource
        details: Additional context (before/after state, etc.)
        ip_address: IP address of the user

    Returns:
        Created AuditLog instance
    """
    audit_log = AuditLog(
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details=details,
        ip_address=ip_address
    )

    db.add(audit_log)
    await db.commit()
    await db.refresh(audit_log)

    logger.info(
        f"Audit log created: user_id={user_id}, action={action}, "
        f"resource_type={resource_type}, resource_id={resource_id}"
    )

    return audit_log
