"""
Timezone utility for consistent datetime handling across all services.

Guatemala uses CST (Central Standard Time) which is UTC-6.
All dates in the system should be timezone-aware using Guatemala timezone.
"""

from datetime import datetime, timezone, timedelta

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
