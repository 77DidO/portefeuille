from __future__ import annotations

import json
from typing import Any, Dict

from app.models.system_logs import SystemLog
from app.utils.time import utc_now


def record_log(db, level: str, component: str, message: str, meta: Dict[str, Any] | None = None) -> None:
    """Persist a structured log entry in the database."""

    log = SystemLog(
        ts=utc_now(),
        level=level,
        component=component,
        message=message,
        meta_json=json.dumps(meta, ensure_ascii=False, sort_keys=True) if meta else None,
    )
    db.add(log)
    db.commit()
