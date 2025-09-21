from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api import deps
from app.models.snapshots import Snapshot
from app.schemas.snapshots import SnapshotRangeResponse
from app.workers.snapshots import run_snapshot

router = APIRouter(prefix="/snapshots", tags=["snapshots"])


@router.get("/", response_model=SnapshotRangeResponse)
def list_snapshots(
    from_ts: Optional[datetime] = Query(default=None, alias="from"),
    to_ts: Optional[datetime] = Query(default=None, alias="to"),
    db: Session = Depends(deps.get_db),
) -> SnapshotRangeResponse:
    query = db.query(Snapshot)
    if from_ts:
        query = query.filter(Snapshot.ts >= from_ts)
    if to_ts:
        query = query.filter(Snapshot.ts <= to_ts)
    snapshots = query.order_by(Snapshot.ts.asc()).all()
    return SnapshotRangeResponse(snapshots=snapshots)


@router.post("/run")
def run_snapshot_now(db: Session = Depends(deps.get_db)) -> dict:
    snapshot = run_snapshot(db)
    return {"snapshot_id": snapshot.id}
