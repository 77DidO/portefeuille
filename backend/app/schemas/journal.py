from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, constr


class JournalTradeBase(BaseModel):
    asset: str
    pair: str
    setup: Optional[str] = None
    entry: Optional[float] = None
    sl: Optional[float] = None
    tp: Optional[float] = None
    risk_r: Optional[float] = None
    status: constr(to_lower=True) = "open"
    result_r: Optional[float] = None
    opened_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    notes: Optional[str] = None


class JournalTradeCreate(JournalTradeBase):
    pass


class JournalTradeUpdate(BaseModel):
    setup: Optional[str]
    entry: Optional[float]
    sl: Optional[float]
    tp: Optional[float]
    risk_r: Optional[float]
    status: Optional[str]
    result_r: Optional[float]
    opened_at: Optional[datetime]
    closed_at: Optional[datetime]
    notes: Optional[str]


class JournalTradeResponse(JournalTradeBase):
    id: int

    class Config:
        orm_mode = True
