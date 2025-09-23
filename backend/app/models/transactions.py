from __future__ import annotations

from sqlalchemy import Column, DateTime, Float, Integer, String, Text, UniqueConstraint

from .base import Base


class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = (
        UniqueConstraint("transaction_uid", name="uq_transactions_transaction_uid"),
    )

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(String(64), nullable=True)
    source = Column(String(32), nullable=False)
    portfolio_type = Column(String(16), nullable=False)
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
    total_eur = Column(Float, nullable=False)
    trade_date = Column(DateTime(timezone=True), nullable=False, index=True)
    notes = Column(Text, nullable=True)
    transaction_uid = Column(String(128), nullable=False)
