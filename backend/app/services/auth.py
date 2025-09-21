from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from passlib.exc import UnknownHashError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import (
    create_access_token,
    get_password_hash,
    pwd_context,
    verify_password,
)
from app.models.settings import Setting
from app.utils.time import utc_now


PASSWORD_KEY = "password_hash"


def _store_password_hash(db: Session, hashed_password: str) -> str:
    setting = db.get(Setting, PASSWORD_KEY)
    if setting:
        setting.value = hashed_password
        setting.updated_at = utc_now()
    else:
        db.add(Setting(key=PASSWORD_KEY, value=hashed_password, updated_at=utc_now()))
    db.commit()
    return hashed_password


def _is_valid_hash(candidate: str) -> bool:
    if not candidate:
        return False

    try:
        handler = pwd_context.handler("bcrypt")
    except KeyError:
        return False

    try:
        handler.from_string(candidate)
    except (ValueError, UnknownHashError):
        return False

    return True


def _default_password_hash(db: Session) -> str:
    return _store_password_hash(db, get_password_hash("admin12345!"))


def _load_password_hash(db: Session) -> str:
    setting = db.get(Setting, PASSWORD_KEY)
    if setting:
        stored_hash = setting.value or ""
        if _is_valid_hash(stored_hash):
            return stored_hash

    configured_hash = settings.password_hash
    if configured_hash and _is_valid_hash(configured_hash):
        return _store_password_hash(db, configured_hash)

    # fallback default password admin12345!
    return _default_password_hash(db)


def authenticate(db: Session, username: str, password: str) -> str:
    if username != "admin":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Identifiants invalides")
    hashed = _load_password_hash(db)
    if not verify_password(password, hashed):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Identifiants invalides")
    expire = timedelta(minutes=settings.access_token_expire_minutes)
    token = create_access_token({"sub": "admin"}, expires_delta=expire)
    return token


def change_password(db: Session, current_password: str, new_password: str) -> None:
    hashed = _load_password_hash(db)
    if not verify_password(current_password, hashed):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Mot de passe actuel invalide")
    new_hash = get_password_hash(new_password)
    setting = db.get(Setting, PASSWORD_KEY)
    if setting:
        setting.value = new_hash
        setting.updated_at = utc_now()
    else:
        db.add(Setting(key=PASSWORD_KEY, value=new_hash, updated_at=utc_now()))
    db.commit()
