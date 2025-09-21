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
