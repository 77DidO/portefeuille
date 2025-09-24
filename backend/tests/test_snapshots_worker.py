from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sys

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.models.base import Base
from app.models.holdings import Holding
from app.models import holdings as holdings_model  # noqa: F401  # ensure table registration
from app.models import snapshots as snapshots_model  # noqa: F401
from app.models import transactions as transactions_model  # noqa: F401
from app.services.portfolio import HoldingView
from app.workers import snapshots


class DummyComputeHoldings:
    def __init__(self, holdings: list[HoldingView], totals: dict[str, float]) -> None:
        self._holdings = holdings
        self._totals = totals

    def __call__(self, db: Session):
        return self._holdings, self._totals

    def cache_clear(self) -> None:
        return None


def test_run_snapshot_separates_pea_crypto_and_other(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine)
    db = TestingSessionLocal()

    try:
        as_of = datetime(2024, 1, 1, tzinfo=timezone.utc)
        holdings = [
            HoldingView(
                identifier="PEA::PEA_POS",
                asset="PEA_POS",
                symbol_or_isin="PEA_POS",
                symbol="PEA_POS",
                isin=None,
                mic=None,
                quantity=1.0,
                pru_eur=100.0,
                invested_eur=100.0,
                market_price_eur=120.0,
                market_value_eur=120.0,
                pl_eur=20.0,
                pl_pct=20.0,
                type_portefeuille="PEA",
                as_of=as_of,
            ),
            HoldingView(
                identifier="CTO::CTO_POS",
                asset="CTO_POS",
                symbol_or_isin="CTO_POS",
                symbol="CTO_POS",
                isin=None,
                mic=None,
                quantity=2.0,
                pru_eur=50.0,
                invested_eur=100.0,
                market_price_eur=80.0,
                market_value_eur=160.0,
                pl_eur=60.0,
                pl_pct=60.0,
                type_portefeuille="CTO",
                as_of=as_of,
            ),
            HoldingView(
                identifier="CRYPTO::BTC",
                asset="BTC",
                symbol_or_isin="BTC",
                symbol="BTC",
                isin=None,
                mic=None,
                quantity=0.1,
                pru_eur=2000.0,
                invested_eur=200.0,
                market_price_eur=3000.0,
                market_value_eur=300.0,
                pl_eur=100.0,
                pl_pct=50.0,
                type_portefeuille="CRYPTO",
                as_of=as_of,
            ),
        ]

        totals = {
            "realized_pnl": 0.0,
            "latent_pnl": sum(holding.pl_eur for holding in holdings),
        }

        dummy_compute = DummyComputeHoldings(holdings, totals)
        monkeypatch.setattr(snapshots, "compute_holdings", dummy_compute)

        snapshot = snapshots.run_snapshot(db)

        assert snapshot.value_pea_eur == 120.0
        assert snapshot.value_crypto_eur == 300.0
        assert snapshot.value_total_eur == 120.0 + 160.0 + 300.0

        persisted = db.query(Holding).all()
        assert len(persisted) == len(holdings)
        assert {holding.snapshot_id for holding in persisted} == {snapshot.id}
    finally:
        db.close()
        engine.dispose()
