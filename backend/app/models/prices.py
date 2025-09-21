from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, DateTime, Float, Integer, String, UniqueConstraint

from .base import Base


class Price(Base):
    __tablename__ = "prices"
    __table_args__ = (
        UniqueConstraint("asset", "ts", "source", name="uq_prices_asset_ts_source"),
    )

    id = Column(Integer, primary_key=True)
    asset = Column(String(64), nullable=False)
    ts = Column(DateTime(timezone=True), nullable=False)
    price_eur = Column(Float, nullable=False)
    source = Column(String(32), nullable=False)
