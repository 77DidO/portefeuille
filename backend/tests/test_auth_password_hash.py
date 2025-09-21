from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.core.config import settings  # noqa: E402
from app.core.security import verify_password  # noqa: E402
from app.models.base import Base  # noqa: E402
from app.models.settings import Setting  # noqa: E402
from app.services import auth as auth_service  # noqa: E402



@pytest.fixture()
def db_session():

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine)
    db = TestingSessionLocal()

    try:
        yield db
    finally:
        db.close()
        engine.dispose()


def test_authenticate_falls_back_to_default_hash_from_config(monkeypatch, db_session):
    placeholder_hash = "$2b$12$replace_with_bcrypt_hash"
    patched_settings = settings.model_copy(update={"password_hash": placeholder_hash})
    monkeypatch.setattr(auth_service, "settings", patched_settings, raising=False)

    token = auth_service.authenticate(db_session, "admin", "admin12345!")
    assert token

    stored_setting = db_session.get(Setting, auth_service.PASSWORD_KEY)
    assert stored_setting is not None
    assert stored_setting.value != placeholder_hash
    assert verify_password("admin12345!", stored_setting.value)


def test_authenticate_recovers_from_invalid_stored_hash(monkeypatch, db_session):
    placeholder_hash = "$2b$12$replace_with_bcrypt_hash"
    db_session.add(
        Setting(
            key=auth_service.PASSWORD_KEY,
            value=placeholder_hash,
            updated_at=datetime.now(timezone.utc),
        )
    )
    db_session.commit()

    monkeypatch.setattr(auth_service, "settings", settings, raising=False)

    token = auth_service.authenticate(db_session, "admin", "admin12345!")
    assert token

    stored_setting = db_session.get(Setting, auth_service.PASSWORD_KEY)
    assert stored_setting is not None
    assert stored_setting.value != placeholder_hash
    assert verify_password("admin12345!", stored_setting.value)

