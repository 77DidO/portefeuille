from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, DateTime, Float, Integer, String, UniqueConstraint

from .base import Base


class FxRate(Base):
    __tablename__ = "fx_rates"
    __table_args__ = (
        UniqueConstraint("ts", "base", "quote", name="uq_fx_rates_ts_base_quote"),
    )

    id = Column(Integer, primary_key=True)
    ts = Column(DateTime(timezone=True), nullable=False)
    base = Column(String(8), nullable=False)
    quote = Column(String(8), nullable=False)
    rate = Column(Float, nullable=False)
    source = Column(String(32), nullable=False)
