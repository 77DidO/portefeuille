from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api import deps
from app.models.snapshots import Snapshot
from app.schemas.portfolio import HoldingResponse, HoldingsResponse, PnLPoint, PnLRangeResponse
from app.schemas.snapshots import SnapshotResponse
from app.services.portfolio import compute_holdings

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


@router.get("/holdings", response_model=HoldingsResponse)
def get_holdings(db: Session = Depends(deps.get_db), _: dict = Depends(deps.get_current_user)) -> HoldingsResponse:
    holdings_raw, totals = compute_holdings(db)
    holdings = [
        HoldingResponse(
            asset=h.asset,
            symbol_or_isin=h.symbol_or_isin,
            quantity=h.quantity,
            pru_eur=h.pru_eur,
            invested_eur=h.invested_eur,
            market_price_eur=h.market_price_eur,
            market_value_eur=h.market_value_eur,
            pl_eur=h.pl_eur,
            pl_pct=h.pl_pct,
            type_portefeuille=h.type_portefeuille,
            as_of=h.as_of,
        )
        for h in holdings_raw
    ]
    summary = {
        "total_value_eur": sum(h.market_value_eur for h in holdings),
        "total_invested_eur": sum(h.invested_eur for h in holdings),
        "pnl_eur": totals["latent_pnl"] + totals["realized_pnl"],
        "pnl_pct": (sum(h.pl_eur for h in holdings) / sum(h.invested_eur for h in holdings) * 100.0)
        if sum(h.invested_eur for h in holdings)
        else 0.0,
    }
    return HoldingsResponse(holdings=holdings, summary=summary)


@router.get("/pnl", response_model=PnLRangeResponse)
def get_pnl(
    range: str = Query("ALL", pattern="^(1M|3M|YTD|ALL)$"),
    db: Session = Depends(deps.get_db),
    _: dict = Depends(deps.get_current_user),
) -> PnLRangeResponse:
    query = db.query(Snapshot).order_by(Snapshot.ts.desc())
    points = [
        PnLPoint(ts=row.ts, value_total_eur=row.value_total_eur, pnl_total_eur=row.pnl_total_eur)
        for row in query.all()
    ]
    return PnLRangeResponse(points=list(reversed(points)))
