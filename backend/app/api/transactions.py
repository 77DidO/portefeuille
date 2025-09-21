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
    if not file.filename.endswith(".zip"):
        raise HTTPException(status_code=400, detail="Format attendu: ZIP")
    importer = Importer(db)
    try:
        importer.import_zip(file.file.read())
    except ImportErrorDetail as exc:
        raise HTTPException(status_code=400, detail=f"Import invalide: {exc}") from exc
    from app.services.portfolio import compute_holdings

    compute_holdings.cache_clear()  # invalidate cache after import
    return {"status": "ok"}
