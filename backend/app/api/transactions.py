from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.api import deps
from app.models.transactions import Transaction
from app.schemas.transactions import TransactionResponse
from app.services.importer import ImportErrorDetail, Importer

router = APIRouter(prefix="/transactions", tags=["transactions"])


@router.get("/", response_model=list[TransactionResponse])
def list_transactions(db: Session = Depends(deps.get_db), _: dict = Depends(deps.get_current_user)):
    return db.query(Transaction).order_by(Transaction.ts.desc()).limit(500).all()


@router.post("/import")
def import_transactions(
    file: UploadFile = File(...),
    db: Session = Depends(deps.get_db),
    _: dict = Depends(deps.get_current_user),
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
