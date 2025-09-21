from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api import deps
from app.models.settings import Setting
from app.schemas.settings import SettingResponse, SettingsPayload
from app.utils.crypto import encrypt
from app.utils.time import utc_now

router = APIRouter(prefix="/config", tags=["config"])


@router.get("/settings", response_model=list[SettingResponse])
def list_settings(db: Session = Depends(deps.get_db), _: dict = Depends(deps.get_current_user)):
    return db.query(Setting).order_by(Setting.key).all()


@router.post("/settings", response_model=list[SettingResponse])
def save_settings(payload: SettingsPayload, db: Session = Depends(deps.get_db), _: dict = Depends(deps.get_current_user)):
    for key, value in payload.data.items():
        setting = db.get(Setting, key)
        if setting:
            setting.value = value
            setting.updated_at = utc_now()
        else:
            db.add(Setting(key=key, value=value, updated_at=utc_now()))
    db.commit()
    return db.query(Setting).order_by(Setting.key).all()


@router.post("/api/binance")
def save_binance_api(credentials: dict, db: Session = Depends(deps.get_db), _: dict = Depends(deps.get_current_user)):
    key = credentials.get("key", "")
    secret = credentials.get("secret", "")
    db.merge(Setting(key="binance_api_key", value=encrypt(key) if key else None, updated_at=utc_now()))
    db.merge(Setting(key="binance_api_secret", value=encrypt(secret) if secret else None, updated_at=utc_now()))
    db.commit()
    return {"status": "ok"}
