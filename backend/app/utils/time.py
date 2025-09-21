from __future__ import annotations

from datetime import datetime

import pytz
from dateutil import tz

from app.core.config import settings


PARIS_TZ = pytz.timezone(settings.tz)


def utc_now() -> datetime:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc)


def to_paris(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=tz.UTC)
    return dt.astimezone(PARIS_TZ)


def to_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=PARIS_TZ)
    return dt.astimezone(tz.UTC)
