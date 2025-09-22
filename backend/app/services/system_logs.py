from __future__ import annotations

import json
import logging
from typing import Any, Dict

from app.models.system_logs import SystemLog
from app.utils.time import utc_now


logger = logging.getLogger("system")
LEVEL_MAP = {name: level for name, level in logging._nameToLevel.items()}


def record_log(db, level: str, component: str, message: str, meta: Dict[str, Any] | None = None) -> None:
    """Persist a structured log entry in the database."""

    log_level = LEVEL_MAP.get(level.upper(), logging.INFO)
    meta_json = json.dumps(meta, ensure_ascii=False, sort_keys=True) if meta else None

    if meta_json:
        logger.log(log_level, "%s | %s | meta=%s", component, message, meta_json)
    else:
        logger.log(log_level, "%s | %s", component, message)

    log = SystemLog(
        ts=utc_now(),
        level=level,
        component=component,
        message=message,
        meta_json=meta_json,
    )
    db.add(log)
    db.commit()
