from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.api import deps
from app.services.exporter import export_zip

router = APIRouter(prefix="/export", tags=["export"])


@router.get("/zip")
def export_zip_route(db: Session = Depends(deps.get_db)):
    content = export_zip(db)
    return Response(content=content, media_type="application/zip", headers={"Content-Disposition": "attachment; filename=portfolio_export.zip"})
