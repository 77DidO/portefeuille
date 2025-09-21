from __future__ import annotations

from datetime import datetime
from typing import List

from pydantic import BaseModel


class SnapshotResponse(BaseModel):
    ts: datetime
    value_pea_eur: float
    value_crypto_eur: float
    value_total_eur: float
    pnl_total_eur: float

    class Config:
        orm_mode = True


class SnapshotRangeResponse(BaseModel):
    snapshots: List[SnapshotResponse]
