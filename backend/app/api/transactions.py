from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy import Date
from sqlalchemy.orm import Session

from app.api import deps
from app.models.transactions import Transaction
from app.schemas.transactions import (
    TransactionDeleteResponse,
    TransactionResponse,
    TransactionUpdate,
)
from app.services.importer import ImportErrorDetail, Importer

router = APIRouter(prefix="/transactions", tags=["transactions"])


@router.get("/", response_model=list[TransactionResponse])
def list_transactions(
    source: str | None = Query(None),
    portfolio_type: str | None = Query(None, alias="type"),
    asset: str | None = Query(None),
    operation: str | None = Query(None),
    symbol: str | None = Query(None),
    isin: str | None = Query(None),
    mic: str | None = Query(None),
    csv_transaction_id: str | None = Query(None, alias="csv_id"),
    transaction_date: date | None = Query(None, alias="date"),
    db: Session = Depends(deps.get_db),
):
    query = db.query(Transaction)

    if source is not None:
        query = query.filter(Transaction.source == source)
    if portfolio_type is not None:
        query = query.filter(Transaction.portfolio_type == portfolio_type)
    if asset is not None:
        query = query.filter(Transaction.asset == asset)
    if operation is not None:
        query = query.filter(Transaction.operation == operation)
    if symbol is not None:
        query = query.filter(Transaction.symbol == symbol)
    if isin is not None:
        query = query.filter(Transaction.isin == isin)
    if mic is not None:
        query = query.filter(Transaction.mic == mic)
    if csv_transaction_id is not None:
        query = query.filter(Transaction.transaction_uid == csv_transaction_id)
    if transaction_date is not None:
        query = query.filter(Transaction.trade_date.cast(Date) == transaction_date)

    return query.order_by(Transaction.trade_date.desc()).limit(500).all()


@router.post("/import")
def import_transactions(
    file: UploadFile = File(...),
    db: Session = Depends(deps.get_db),
) -> dict:
    filename = (file.filename or "").lower()
    if not filename.endswith((".zip", ".csv")):
        raise HTTPException(status_code=400, detail="Format attendu: ZIP ou CSV")

    importer = Importer(db)
    content = file.file.read()
    try:
        if filename.endswith(".zip"):
            importer.import_zip(content)
        else:
            importer.import_transactions_csv(content)
    except ImportErrorDetail as exc:
        detail: dict[str, object] = {"message": exc.detailed_message}
        if exc.row_number is not None:
            detail["row_number"] = exc.row_number
        raise HTTPException(status_code=400, detail=detail) from exc
    from app.services.portfolio import compute_holdings

    compute_holdings.cache_clear()  # invalidate cache after import
    return {"status": "ok"}


@router.patch("/{transaction_id}", response_model=TransactionResponse)
def update_transaction(
    transaction_id: int,
    payload: TransactionUpdate,
    db: Session = Depends(deps.get_db),
) -> Transaction:
    transaction = db.get(Transaction, transaction_id)
    if transaction is None:
        raise HTTPException(status_code=404, detail="Transaction introuvable")

    updates = payload.to_orm_updates(getattr(transaction.trade_date, "tzinfo", None))
    for field, value in updates.items():
        setattr(transaction, field, value)

    db.add(transaction)
    db.commit()
    db.refresh(transaction)

    from app.services.portfolio import compute_holdings

    compute_holdings.cache_clear()
    return transaction


@router.delete("/{transaction_id}", response_model=TransactionDeleteResponse)
def delete_transaction(
    transaction_id: int,
    db: Session = Depends(deps.get_db),
) -> TransactionDeleteResponse:
    transaction = db.get(Transaction, transaction_id)
    if transaction is None:
        raise HTTPException(status_code=404, detail="Transaction introuvable")

    db.delete(transaction)
    db.commit()

    from app.services.portfolio import compute_holdings

    compute_holdings.cache_clear()
    return TransactionDeleteResponse(status="ok")
