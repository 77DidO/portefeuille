from __future__ import annotations

import csv
import io
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.models.base import Base
from app.models.holdings import Holding
from app.models import holdings as holdings_model  # noqa: F401  # ensure table registration
from app.models import journal_trades as journal_trades_model  # noqa: F401
from app.models import snapshots as snapshots_model  # noqa: F401
from app.models import transactions as transactions_model  # noqa: F401
from app.services.exporter import export_zip
from app.services.portfolio import HoldingView
from app.workers import snapshots


class DummyComputeHoldings:
    def __init__(self, holdings: list[HoldingView], totals: dict[str, float]) -> None:
        self._holdings = holdings
        self._totals = totals

    def __call__(self, db: Session):
        return self._holdings, self._totals

    def cache_clear(self) -> None:
        # The production function exposes a cache_clear attribute; the worker
        # invokes it before computing the snapshot. The dummy implementation does
        # nothing but keeps the same interface.
        return None


def test_export_holdings_uses_persisted_portfolio_type(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine)
    db = TestingSessionLocal()

    try:
        as_of = datetime(2024, 1, 1, tzinfo=timezone.utc)
        holding_view = HoldingView(
            identifier="CRYPTO::SOL",
            asset="SOL",
            symbol_or_isin="SOL",
            symbol="SOL",
            isin=None,
            mic=None,
            quantity=2.0,
            pru_eur=10.0,
            invested_eur=20.0,
            market_price_eur=15.0,
            market_value_eur=30.0,
            pl_eur=10.0,
            pl_pct=50.0,
            type_portefeuille="CRYPTO",
            as_of=as_of,
        )

        totals = {"realized_pnl": 0.0, "latent_pnl": holding_view.pl_eur}
        dummy_compute = DummyComputeHoldings([holding_view], totals)
        monkeypatch.setattr(snapshots, "compute_holdings", dummy_compute)

        snapshot = snapshots.run_snapshot(db)

        stored_holding = db.query(Holding).filter_by(asset="SOL").one()
        assert stored_holding.portfolio_type == "CRYPTO"
        assert stored_holding.symbol == "SOL"
        assert stored_holding.snapshot_id == snapshot.id

        archive = export_zip(db)
        with zipfile.ZipFile(io.BytesIO(archive)) as zf:
            with zf.open("holdings.csv") as holdings_file:
                reader = csv.DictReader(io.TextIOWrapper(holdings_file, encoding="utf-8"))
                rows = list(reader)

        assert any(
            row["asset"] == "SOL"
            and row["portfolio_type"] == "CRYPTO"
            and row["symbol"] == "SOL"
            and row["snapshot_id"] == str(snapshot.id)
            for row in rows
        )
    finally:
        db.close()
        engine.dispose()
