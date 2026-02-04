"""
Timezone utility for consistent datetime handling across all services.

Guatemala uses CST (Central Standard Time) which is UTC-6.
All dates in the system should be timezone-aware using Guatemala timezone.
"""

from datetime import datetime, timezone, timedelta
from typing import Optional

# Guatemala timezone: UTC-6 (CST - Central Standard Time)
# Guatemala does not observe daylight saving time
GUATEMALA_TZ = timezone(timedelta(hours=-6))
GUATEMALA_TZ_NAME = "America/Guatemala"


def now_gt() -> datetime:
    """
    Get current datetime in Guatemala timezone (UTC-6).

    Returns:
        datetime: Current datetime with Guatemala timezone info
    """
    return datetime.now(GUATEMALA_TZ)


def utc_to_gt(dt: datetime) -> datetime:
    """
    Convert a UTC datetime to Guatemala timezone.

    Args:
        dt: UTC datetime (can be naive or aware)

    Returns:
        datetime: Datetime converted to Guatemala timezone
    """
    if dt.tzinfo is None:
        # Assume naive datetime is UTC
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(GUATEMALA_TZ)


def make_aware_gt(dt: datetime) -> datetime:
    """
    Make a naive datetime timezone-aware using Guatemala timezone.
    If datetime is already aware, return it as-is.

    Args:
        dt: Naive or aware datetime

    Returns:
        datetime: Timezone-aware datetime in Guatemala timezone
    """
    if dt.tzinfo is None:
        return dt.replace(tzinfo=GUATEMALA_TZ)
    return dt.astimezone(GUATEMALA_TZ)


def today_gt():
    """
    Get today's date in Guatemala timezone.

    Returns:
        date: Today's date in Guatemala timezone
    """
    return now_gt().date()


def datetime_gt(
    year: int,
    month: int,
    day: int,
    hour: int = 0,
    minute: int = 0,
    second: int = 0,
    microsecond: int = 0
) -> datetime:
    """
    Create a timezone-aware datetime in Guatemala timezone.

    Args:
        year: Year
        month: Month (1-12)
        day: Day (1-31)
        hour: Hour (0-23), default 0
        minute: Minute (0-59), default 0
        second: Second (0-59), default 0
        microsecond: Microsecond (0-999999), default 0

    Returns:
        datetime: Timezone-aware datetime in Guatemala timezone
    """
    return datetime(
        year, month, day, hour, minute, second, microsecond,
        tzinfo=GUATEMALA_TZ
    )
