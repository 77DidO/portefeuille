from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, Text

from .base import Base


class SystemLog(Base):
    __tablename__ = "system_logs"

    id = Column(Integer, primary_key=True)
    ts = Column(DateTime(timezone=True), nullable=False)
    level = Column(String(16), nullable=False)
    component = Column(String(64), nullable=False)
    message = Column(String(255), nullable=False)
    meta_json = Column(Text, nullable=True)
