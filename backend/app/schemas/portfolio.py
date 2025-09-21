from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class HoldingBase(BaseModel):
    asset: str
    symbol_or_isin: Optional[str] = None
    quantity: float
    pru_eur: float
    invested_eur: float
    market_price_eur: float
    market_value_eur: float
    pl_eur: float
    pl_pct: float
    type_portefeuille: str


class HoldingResponse(HoldingBase):
    as_of: datetime

    class Config:
        orm_mode = True


class HoldingSummary(BaseModel):
    total_value_eur: float
    total_invested_eur: float
    pnl_eur: float
    pnl_pct: float


class HoldingsResponse(BaseModel):
    holdings: List[HoldingResponse]
    summary: HoldingSummary


class PnLPoint(BaseModel):
    ts: datetime
    value_total_eur: float
    pnl_total_eur: float


class PnLRangeResponse(BaseModel):
    points: List[PnLPoint]
