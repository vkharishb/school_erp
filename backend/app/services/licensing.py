from datetime import UTC, datetime

PHASE1_MODULES = [
    "dashboard",
    "school_admin",
    "school_config",
    "student",
    "teacher",
    "fee",
    "marks",
    "attendance",
    "reports",
]

# Subscription policy: there are no mandatory/Core ERP business modules.
# Each plan carries the exact module entitlement approved by the Platform Owner.
# PHASE1_MODULES remains only a delivery-status/legacy catalog constant.

def next_may_31(now: datetime | None = None) -> datetime:
    """Return 31-May 23:59:59 IST as an aware UTC datetime.

    India Standard Time is UTC+05:30 year-round, so 31-May 23:59:59 IST
    is 31-May 18:29:59 UTC. Keeping this calculation in UTC avoids a
    platform dependency on the IANA tzdata database on Windows.
    """
    now = now or datetime.now(UTC)
    year = now.year if (now.month, now.day) <= (5, 31) else now.year + 1
    return datetime(year, 5, 31, 18, 29, 59, tzinfo=UTC)


IMPLEMENTED_MODULES = set(PHASE1_MODULES)
