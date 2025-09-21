from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, DateTime, Float, Integer, String, Text

from .base import Base


class JournalTrade(Base):
    __tablename__ = "journal_trades"

    id = Column(Integer, primary_key=True)
    asset = Column(String(64), nullable=False)
    pair = Column(String(32), nullable=False)
    setup = Column(String(64), nullable=True)
    entry = Column(Float, nullable=True)
    sl = Column(Float, nullable=True)
    tp = Column(Float, nullable=True)
    risk_r = Column(Float, nullable=True)
    result_r = Column(Float, nullable=True)
    status = Column(String(16), nullable=False, default="OPEN")
    opened_at = Column(DateTime(timezone=True), nullable=True)
    closed_at = Column(DateTime(timezone=True), nullable=True)
    notes = Column(Text, nullable=True)
