from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api import deps
from app.core.config import settings
from app.schemas.auth import ChangePasswordRequest, LoginRequest, Token
from app.services import auth as auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=Token)
def login(payload: LoginRequest, db: Session = Depends(deps.get_db)) -> Token:
    token = auth_service.authenticate(db, payload.username, payload.password)
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    return Token(access_token=token, expires_at=expires_at)


@router.post("/change-password")
def change_password(
    payload: ChangePasswordRequest,
    _: dict = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
) -> dict:
    auth_service.change_password(db, payload.current_password, payload.new_password)
    return {"status": "ok"}
