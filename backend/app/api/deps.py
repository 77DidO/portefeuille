from __future__ import annotations

from fastapi import Depends

from app.db.session import get_db


__all__ = ["get_db"]
