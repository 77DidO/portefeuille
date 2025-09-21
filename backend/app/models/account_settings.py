from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, Text

from .base import Base


class AccountSetting(Base):
    __tablename__ = "account_settings"

    id = Column(Integer, primary_key=True)
    account_id = Column(String(64), nullable=False)
    key = Column(String(64), nullable=False)
    value = Column(Text, nullable=True)
    updated_at = Column(DateTime(timezone=True), nullable=False)
