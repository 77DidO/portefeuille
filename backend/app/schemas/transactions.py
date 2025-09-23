from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, constr


class TransactionBase(BaseModel):
    source: str
    portfolio_type: constr(to_lower=True)
    operation: str
    asset: str
    symbol_or_isin: Optional[str]
    symbol: Optional[str] = None
    isin: Optional[str] = None
    mic: Optional[str] = None
    quantity: float
    unit_price_eur: float
    fee_eur: float
    fee_asset: Optional[str] = None
    fee_quantity: Optional[float] = None
    total_eur: float
    trade_date: datetime
    notes: Optional[str]
    transaction_uid: Optional[str]


class TransactionCreate(TransactionBase):
    pass


class TransactionResponse(TransactionBase):
    id: int

    class Config:
        orm_mode = True


class TransactionUpdate(BaseModel):
    source: str | None = None
    portfolio_type: constr(to_lower=True) | None = None
    operation: str | None = None
    asset: str | None = None
    symbol_or_isin: Optional[str] = None
    symbol: Optional[str] = None
    isin: Optional[str] = None
    mic: Optional[str] = None
    quantity: float | None = None
    unit_price_eur: float | None = None
    fee_eur: float | None = None
    fee_asset: Optional[str] = None
    fee_quantity: Optional[float] = None
    total_eur: float | None = None
    trade_date: datetime | None = None
    notes: Optional[str] = None
    transaction_uid: Optional[str] = None


class TransactionDeleteResponse(BaseModel):
    status: str
