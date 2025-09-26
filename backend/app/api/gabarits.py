from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api import deps
from app.models.gabarits import Gabarit
from app.schemas.gabarits import GabaritCreate, GabaritResponse, GabaritUpdate

router = APIRouter(prefix="/gabarits", tags=["gabarits"])


@router.get("/", response_model=list[GabaritResponse])
def list_gabarits(db: Session = Depends(deps.get_db)) -> list[Gabarit]:
    return db.query(Gabarit).order_by(Gabarit.nom.asc()).all()


@router.get("/{gabarit_id}", response_model=GabaritResponse)
def get_gabarit(gabarit_id: int, db: Session = Depends(deps.get_db)) -> Gabarit:
    gabarit = db.get(Gabarit, gabarit_id)
    if gabarit is None:
        raise HTTPException(status_code=404, detail="Gabarit introuvable")
    return gabarit


@router.post("/", response_model=GabaritResponse, status_code=201)
def create_gabarit(payload: GabaritCreate, db: Session = Depends(deps.get_db)) -> Gabarit:
    exists = db.query(Gabarit).filter(Gabarit.nom == payload.nom).first()
    if exists is not None:
        raise HTTPException(status_code=400, detail="Un gabarit avec ce nom existe déjà")

    gabarit = Gabarit(
        nom=payload.nom,
        description=payload.description,
        contenu=payload.contenu,
        metadonnees=payload.metadonnees,
    )
    db.add(gabarit)
    db.commit()
    db.refresh(gabarit)
    return gabarit


@router.patch("/{gabarit_id}", response_model=GabaritResponse)
def update_gabarit(
    gabarit_id: int,
    payload: GabaritUpdate,
    db: Session = Depends(deps.get_db),
) -> Gabarit:
    gabarit = db.get(Gabarit, gabarit_id)
    if gabarit is None:
        raise HTTPException(status_code=404, detail="Gabarit introuvable")

    data = payload.model_dump(exclude_unset=True)

    if "nom" in data:
        exists = (
            db.query(Gabarit)
            .filter(Gabarit.nom == data["nom"], Gabarit.id != gabarit_id)
            .first()
        )
        if exists is not None:
            raise HTTPException(status_code=400, detail="Un gabarit avec ce nom existe déjà")

    for field, value in data.items():
        setattr(gabarit, field, value)

    db.add(gabarit)
    db.commit()
    db.refresh(gabarit)
    return gabarit


@router.delete("/{gabarit_id}")
def delete_gabarit(gabarit_id: int, db: Session = Depends(deps.get_db)) -> dict[str, str]:
    gabarit = db.get(Gabarit, gabarit_id)
    if gabarit is None:
        raise HTTPException(status_code=404, detail="Gabarit introuvable")

    db.delete(gabarit)
    db.commit()
    return {"status": "ok"}
