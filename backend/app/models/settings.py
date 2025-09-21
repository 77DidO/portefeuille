from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, DateTime, String, Text

from .base import Base


class Setting(Base):
    __tablename__ = "settings"

    key = Column(String(64), primary_key=True)
    value = Column(Text, nullable=True)
    updated_at = Column(DateTime(timezone=True), nullable=False)
