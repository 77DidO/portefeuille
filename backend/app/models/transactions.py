from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, DateTime, Float, Integer, String, Text, UniqueConstraint

from .base import Base


class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = (
        UniqueConstraint("external_ref", name="uq_transactions_external_ref"),
    )

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(String(64), nullable=True)
    source = Column(String(32), nullable=False)
    type_portefeuille = Column(String(16), nullable=False)
    operation = Column(String(16), nullable=False)
    asset = Column(String(64), nullable=False)
    symbol_or_isin = Column(String(64), nullable=True)
    symbol = Column(String(64), nullable=True)
    isin = Column(String(32), nullable=True)
    mic = Column(String(16), nullable=True)
    quantity = Column(Float, nullable=False)
    unit_price_eur = Column(Float, nullable=False)
    fee_eur = Column(Float, nullable=False, default=0.0)
    fee_asset = Column(String(64), nullable=True)
    fee_quantity = Column(Float, nullable=True)
    fx_rate = Column(Float, nullable=True, default=1.0, server_default="1.0")
    total_eur = Column(Float, nullable=False)
    ts = Column(DateTime(timezone=True), nullable=False, index=True)
    notes = Column(Text, nullable=True)
    external_ref = Column(String(128), nullable=False)
