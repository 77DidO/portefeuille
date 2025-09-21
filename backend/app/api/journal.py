from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api import deps
from app.models.journal_trades import JournalTrade
from app.schemas.journal import JournalTradeCreate, JournalTradeResponse, JournalTradeUpdate

router = APIRouter(prefix="/journal", tags=["journal"])


@router.get("/", response_model=list[JournalTradeResponse])
def list_trades(db: Session = Depends(deps.get_db), _: dict = Depends(deps.get_current_user)):
    return db.query(JournalTrade).order_by(JournalTrade.id.desc()).all()


@router.post("/", response_model=JournalTradeResponse)
def create_trade(payload: JournalTradeCreate, db: Session = Depends(deps.get_db), _: dict = Depends(deps.get_current_user)):
    trade = JournalTrade(**payload.dict())
    db.add(trade)
    db.commit()
    db.refresh(trade)
    return trade


@router.patch("/{trade_id}", response_model=JournalTradeResponse)
def update_trade(
    trade_id: int,
    payload: JournalTradeUpdate,
    db: Session = Depends(deps.get_db),
    _: dict = Depends(deps.get_current_user),
):
    trade = db.get(JournalTrade, trade_id)
    if not trade:
        raise HTTPException(status_code=404, detail="Trade introuvable")
    for key, value in payload.dict(exclude_unset=True).items():
        setattr(trade, key, value)
    db.commit()
    db.refresh(trade)
    return trade
