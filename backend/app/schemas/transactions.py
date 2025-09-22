from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, constr


class TransactionBase(BaseModel):
    source: str
    type_portefeuille: constr(to_lower=True)
    operation: str
    asset: str
    symbol_or_isin: Optional[str]
    quantity: float
    unit_price_eur: float
    fee_eur: float
    fee_asset: Optional[str] = None
    fx_rate: Optional[float] = 1.0
    total_eur: float
    ts: datetime
    notes: Optional[str]
    external_ref: Optional[str]


class TransactionCreate(TransactionBase):
    pass


class TransactionResponse(TransactionBase):
    id: int

    class Config:
        orm_mode = True


class TransactionUpdate(BaseModel):
    source: str | None = None
    type_portefeuille: constr(to_lower=True) | None = None
    operation: str | None = None
    asset: str | None = None
    symbol_or_isin: Optional[str] = None
    quantity: float | None = None
    unit_price_eur: float | None = None
    fee_eur: float | None = None
    fee_asset: Optional[str] = None
    fx_rate: float | None = None
    total_eur: float | None = None
    ts: datetime | None = None
    notes: Optional[str] = None
    external_ref: Optional[str] = None


class TransactionDeleteResponse(BaseModel):
    status: str
