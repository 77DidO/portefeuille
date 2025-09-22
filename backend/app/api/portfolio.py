from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api import deps
from app.models.snapshots import Snapshot
from app.schemas.portfolio import (
    HoldingDetailResponse,
    HoldingHistoryPoint,
    HoldingResponse,
    HoldingsResponse,
    PnLPoint,
    PnLRangeResponse,
)
from app.schemas.snapshots import SnapshotResponse
from app.services.portfolio import HoldingNotFound, compute_holding_detail, compute_holdings

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


@router.get("/holdings", response_model=HoldingsResponse)
def get_holdings(db: Session = Depends(deps.get_db)) -> HoldingsResponse:
    holdings_raw, totals = compute_holdings(db)
    holdings = [
        HoldingResponse(
            identifier=h.identifier,
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
            account_id=h.account_id,
        )
        for h in holdings_raw
    ]
    total_value = sum(h.market_value_eur for h in holdings)
    total_invested = sum(h.invested_eur for h in holdings)
    summary = {
        "total_value_eur": total_value,
        "total_invested_eur": total_invested,
        "pnl_eur": total_value - total_invested,
        "pnl_pct": (sum(h.pl_eur for h in holdings) / sum(h.invested_eur for h in holdings) * 100.0)
        if sum(h.invested_eur for h in holdings)
        else 0.0,
    }
    return HoldingsResponse(holdings=holdings, summary=summary)


@router.get("/holdings/{identifier}", response_model=HoldingDetailResponse)
def get_holding_detail(
    identifier: str,
    db: Session = Depends(deps.get_db),
) -> HoldingDetailResponse:
    try:
        detail = compute_holding_detail(db, identifier)
    except HoldingNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    history = [
        HoldingHistoryPoint(
            ts=point.ts,
            quantity=point.quantity,
            invested_eur=point.invested_eur,
            market_price_eur=point.market_price_eur,
            market_value_eur=point.market_value_eur,
            pl_eur=point.pl_eur,
            pl_pct=point.pl_pct,
            operation=point.operation,
        )
        for point in detail.history
    ]

    return HoldingDetailResponse(
        identifier=detail.identifier,
        asset=detail.asset,
        symbol_or_isin=detail.symbol_or_isin,
        quantity=detail.quantity,
        pru_eur=detail.pru_eur,
        invested_eur=detail.invested_eur,
        market_price_eur=detail.market_price_eur,
        market_value_eur=detail.market_value_eur,
        pl_eur=detail.pl_eur,
        pl_pct=detail.pl_pct,
        type_portefeuille=detail.type_portefeuille,
        as_of=detail.as_of,
        account_id=detail.account_id,
        history=history,
        realized_pnl_eur=detail.realized_pnl_eur,
        dividends_eur=detail.dividends_eur,
        history_available=detail.history_available,
    )


@router.get("/pnl", response_model=PnLRangeResponse)
def get_pnl(
    db: Session = Depends(deps.get_db),
) -> PnLRangeResponse:
    query = db.query(Snapshot).order_by(Snapshot.ts.desc())
    points = [
        PnLPoint(ts=row.ts, value_total_eur=row.value_total_eur, pnl_total_eur=row.pnl_total_eur)
        for row in query.all()
    ]
    return PnLRangeResponse(points=list(reversed(points)))
