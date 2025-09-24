from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship, synonym

from .base import Base


class Holding(Base):
    __tablename__ = "holdings"

    id = Column(Integer, primary_key=True)
    account_id = Column(String(64), nullable=True)
    snapshot_id = Column(
        Integer,
        ForeignKey("snapshots.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    asset = Column(String(64), nullable=False)
    symbol_or_isin = Column(String(64), nullable=True)
    symbol = Column(String(64), nullable=True)
    isin = Column(String(32), nullable=True)
    mic = Column(String(16), nullable=True)
    quantity = Column(Float, nullable=False)
    pru_eur = Column(Float, nullable=False)
    invested_eur = Column(Float, nullable=False)
    market_price_eur = Column(Float, nullable=False)
    market_value_eur = Column(Float, nullable=False)
    pl_eur = Column(Float, nullable=False)
    pl_pct = Column(Float, nullable=False)
    as_of = Column(DateTime(timezone=True), nullable=False, index=True)
    portfolio_type = Column(String(16), nullable=False)
    type_portefeuille = synonym("portfolio_type")
    snapshot = relationship("Snapshot", back_populates="holdings")
