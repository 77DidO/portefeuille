from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings
from app.core.security import decode_access_token
from app.db.session import get_db

security = HTTPBearer(auto_error=True)


async def get_current_user(credentials: Annotated[HTTPAuthorizationCredentials, Security(security)]):
    token = credentials.credentials
    try:
        payload = decode_access_token(token)
    except ValueError as exc:  # noqa: BLE001
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token invalide") from exc
    if payload.get("sub") != "admin":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Utilisateur inconnu")
    return {"username": "admin"}


__all__ = ["get_db", "get_current_user"]
