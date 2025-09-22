from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
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
    type_portefeuille: str | None = Query(None, alias="type"),
    asset: str | None = Query(None),
    operation: str | None = Query(None),
    db: Session = Depends(deps.get_db),
):
    query = db.query(Transaction)

    if source is not None:
        query = query.filter(Transaction.source == source)
    if type_portefeuille is not None:
        query = query.filter(Transaction.type_portefeuille == type_portefeuille)
    if asset is not None:
        query = query.filter(Transaction.asset == asset)
    if operation is not None:
        query = query.filter(Transaction.operation == operation)

    return query.order_by(Transaction.ts.desc()).limit(500).all()


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

    updates = payload.dict(exclude_unset=True)
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
