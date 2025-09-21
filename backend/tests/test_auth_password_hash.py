from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.core.config import settings  # noqa: E402
from app.core.security import verify_password  # noqa: E402
from app.models.base import Base  # noqa: E402
from app.models.settings import Setting  # noqa: E402
from app.services import auth as auth_service  # noqa: E402


def test_authenticate_falls_back_to_default_hash(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine)
    db = TestingSessionLocal()

    try:
        placeholder_hash = "$2b$12$replace_with_bcrypt_hash"
        patched_settings = settings.model_copy(update={"password_hash": placeholder_hash})
        monkeypatch.setattr(auth_service, "settings", patched_settings, raising=False)

        token = auth_service.authenticate(db, "admin", "admin12345!")
        assert token

        stored_setting = db.get(Setting, auth_service.PASSWORD_KEY)
        assert stored_setting is not None
        assert stored_setting.value != placeholder_hash
        assert verify_password("admin12345!", stored_setting.value)
    finally:
        db.close()
        engine.dispose()
