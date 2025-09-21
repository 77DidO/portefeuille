from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Portefeuille PEA + Crypto"
    database_url: str = Field("sqlite:///./portfolio.db", env="DATABASE_URL")
    tz: str = Field("Europe/Paris", env="TZ")

    app_secret: str = Field("change_me", env="APP_SECRET")
    jwt_secret: str = Field("change_me_jwt", env="JWT_SECRET")
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 12 * 60

    password_hash: str = Field("", env="PASSWORD_HASH")

    binance_api_key: str = Field("", env="BINANCE_API_KEY")
    binance_api_secret: str = Field("", env="BINANCE_API_SECRET")

    scheduler_timezone: str = Field("Europe/Paris")
    snapshot_hour: int = 18
    snapshot_minute: int = 0
    crypto_refresh_seconds: int = 10

    cors_origins: List[str] = Field(default_factory=lambda: ["http://localhost:3000"])

    log_level: str = Field("INFO", env="LOG_LEVEL")
    demo_seed: bool = Field(True, env="DEMO_SEED")

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)

    @field_validator("database_url", mode="before")
    def expand_sqlite_path(cls, v: str) -> str:
        if v.startswith("sqlite") and "///" in v and not v.startswith("sqlite:////"):
            path = v.split("///", 1)[1]
            if not path.startswith("/"):
                abs_path = Path(os.getcwd()) / path
                return f"sqlite:///{abs_path}"
        return v


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
