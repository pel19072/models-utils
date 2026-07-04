# utils/token_utils.py
"""Shared helpers for opaque, single-use tokens (email confirmation, password reset)."""

import uuid
from datetime import datetime
from typing import Optional

from database_utils.utils.timezone_utils import now_gt


def generate_token() -> str:
    """Generate a unique, unguessable token string for email links."""
    return uuid.uuid4().hex


def is_token_valid(expires_at: datetime, used_at: Optional[datetime]) -> bool:
    """A token is valid if it has not been used and has not expired."""
    if used_at is not None:
        return False
    return expires_at > now_gt()
