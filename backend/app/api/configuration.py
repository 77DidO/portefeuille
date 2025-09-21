from __future__ import annotations

import json
from typing import Any

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
from app.services.portfolio import compute_holdings, clear_quote_alias_cache
from app.utils.settings_keys import QUOTE_ALIAS_SETTING_KEY

router = APIRouter(prefix="/config", tags=["config"])


def _serialize_setting_value(key: str, value: Any) -> str | None:
    if value is None:
        return None
    if key == QUOTE_ALIAS_SETTING_KEY and isinstance(value, dict):
        return json.dumps(value)
    if isinstance(value, str):
        return value
    return json.dumps(value)


def _deserialize_setting_value(key: str, value: str | None) -> Any:
    if key == QUOTE_ALIAS_SETTING_KEY and value:
        try:
            loaded = json.loads(value)
        except json.JSONDecodeError:
            return {}
        if isinstance(loaded, dict):
            return {str(k).upper(): str(v) for k, v in loaded.items() if isinstance(k, str) and isinstance(v, str)}
        return {}
    return value


@router.get("/settings", response_model=list[SettingResponse])
def list_settings(db: Session = Depends(deps.get_db)):
    settings = db.query(Setting).order_by(Setting.key).all()
    return [
        SettingResponse(
            key=setting.key,
            value=_deserialize_setting_value(setting.key, setting.value),
            updated_at=setting.updated_at,
        )
        for setting in settings
    ]


@router.post("/settings", response_model=list[SettingResponse])
def save_settings(payload: SettingsPayload, db: Session = Depends(deps.get_db)):
    alias_updated = False
    for key, value in payload.data.items():
        setting = db.get(Setting, key)
        serialized = _serialize_setting_value(key, value)
        if setting:
            setting.value = serialized
            setting.updated_at = utc_now()
        else:
            db.add(Setting(key=key, value=serialized, updated_at=utc_now()))
        if key == QUOTE_ALIAS_SETTING_KEY:
            alias_updated = True
    db.commit()
    if alias_updated:
        clear_quote_alias_cache()
    settings = db.query(Setting).order_by(Setting.key).all()
    return [
        SettingResponse(
            key=setting.key,
            value=_deserialize_setting_value(setting.key, setting.value),
            updated_at=setting.updated_at,
        )
        for setting in settings
    ]


@router.post("/api/binance")
def save_binance_api(credentials: dict, db: Session = Depends(deps.get_db)):
    key = credentials.get("key", "")
    secret = credentials.get("secret", "")
    db.merge(Setting(key="binance_api_key", value=encrypt(key) if key else None, updated_at=utc_now()))
    db.merge(Setting(key="binance_api_secret", value=encrypt(secret) if secret else None, updated_at=utc_now()))
    db.commit()
    return {"status": "ok"}


@router.post("/wipe")
def wipe_data(db: Session = Depends(deps.get_db)) -> dict:
    for model in (Transaction, Snapshot, Holding, JournalTrade, Price, FxRate, AccountSetting, SystemLog):
        db.query(model).delete(synchronize_session=False)
    compute_holdings.cache_clear()
    db.commit()
    return {"status": "ok"}
