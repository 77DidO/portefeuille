from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api import deps
from app.models.account_settings import AccountSetting
from app.models.holdings import Holding
from app.models.journal_trades import JournalTrade
from app.models.fx_rates import FxRate
from app.models.prices import Price
from app.models.snapshots import Snapshot
from app.models.settings import Setting
from app.models.system_logs import SystemLog
from app.models.transactions import Transaction
from app.schemas.settings import SettingResponse, SettingsPayload
from app.utils.crypto import encrypt
from app.utils.time import utc_now
from app.services.portfolio import compute_holdings

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


@router.post("/wipe")
def wipe_data(db: Session = Depends(deps.get_db), _: dict = Depends(deps.get_current_user)) -> dict:
    for model in (Transaction, Snapshot, Holding, JournalTrade, Price, FxRate, AccountSetting, SystemLog):
        db.query(model).delete(synchronize_session=False)
    compute_holdings.cache_clear()
    db.commit()
    return {"status": "ok"}
