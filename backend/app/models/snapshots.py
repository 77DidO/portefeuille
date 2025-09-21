from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, DateTime, Float, Integer, UniqueConstraint

from .base import Base


class Snapshot(Base):
    __tablename__ = "snapshots"

    id = Column(Integer, primary_key=True)
    ts = Column(DateTime(timezone=True), nullable=False, unique=True, index=True)
    value_pea_eur = Column(Float, nullable=False)
    value_crypto_eur = Column(Float, nullable=False)
    value_total_eur = Column(Float, nullable=False)
    pnl_total_eur = Column(Float, nullable=False)
