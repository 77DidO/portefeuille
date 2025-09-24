from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sys

import pytest
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


@pytest.fixture
def in_memory_db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine)
    db = TestingSessionLocal()

    try:
        yield db
    finally:
        db.close()
        engine.dispose()


@pytest.fixture
def as_of() -> datetime:
    return datetime(2024, 1, 1, tzinfo=timezone.utc)


@pytest.fixture
def base_holdings(as_of: datetime) -> list[HoldingView]:
    return [
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


@pytest.fixture
def holdings_with_variants(as_of: datetime) -> list[HoldingView]:
    return [
        HoldingView(
            identifier="PEA-PME::POS",
            asset="PEA_PME_POS",
            symbol_or_isin="PEA_PME_POS",
            symbol="PEA_PME_POS",
            isin=None,
            mic=None,
            quantity=1.0,
            pru_eur=200.0,
            invested_eur=200.0,
            market_price_eur=250.0,
            market_value_eur=250.0,
            pl_eur=50.0,
            pl_pct=25.0,
            type_portefeuille="PEA-PME",
            as_of=as_of,
        ),
        HoldingView(
            identifier="PEAJEUNE::POS",
            asset="PEAJEUNE_POS",
            symbol_or_isin="PEAJEUNE_POS",
            symbol="PEAJEUNE_POS",
            isin=None,
            mic=None,
            quantity=2.0,
            pru_eur=150.0,
            invested_eur=300.0,
            market_price_eur=200.0,
            market_value_eur=400.0,
            pl_eur=100.0,
            pl_pct=33.3333,
            type_portefeuille="PEAJEUNE",
            as_of=as_of,
        ),
        HoldingView(
            identifier="CRYPTO BINANCE::ETH",
            asset="ETH",
            symbol_or_isin="ETH",
            symbol="ETH",
            isin=None,
            mic=None,
            quantity=1.0,
            pru_eur=1000.0,
            invested_eur=1000.0,
            market_price_eur=1500.0,
            market_value_eur=1500.0,
            pl_eur=500.0,
            pl_pct=50.0,
            type_portefeuille="CRYPTO BINANCE",
            as_of=as_of,
        ),
    ]


@pytest.fixture
def capture_logs(monkeypatch):
    calls: list[tuple[str, str, str, dict | None]] = []

    def fake_record_log(db, level, category, message, meta=None):
        calls.append((level, category, message, meta))

    monkeypatch.setattr(snapshots, "record_log", fake_record_log)
    return calls


def _build_dummy_compute(holdings: list[HoldingView]) -> DummyComputeHoldings:
    totals = {
        "realized_pnl": 0.0,
        "latent_pnl": sum(holding.pl_eur for holding in holdings),
    }
    return DummyComputeHoldings(holdings, totals)


def test_run_snapshot_separates_pea_crypto_and_other(
    in_memory_db: Session,
    base_holdings: list[HoldingView],
    monkeypatch: pytest.MonkeyPatch,
    capture_logs: list[tuple[str, str, str, dict | None]],
):
    dummy_compute = _build_dummy_compute(base_holdings)
    monkeypatch.setattr(snapshots, "compute_holdings", dummy_compute)

    snapshot = snapshots.run_snapshot(in_memory_db)

    assert snapshot.value_pea_eur == 120.0
    assert snapshot.value_crypto_eur == 300.0
    assert snapshot.value_total_eur == 120.0 + 160.0 + 300.0

    completed_log = capture_logs[-1]
    assert completed_log[3]["snapshot"]["value_pea_eur"] == 120.0
    assert completed_log[3]["snapshot"]["value_crypto_eur"] == 300.0


def test_run_snapshot_normalizes_portfolio_variants(
    in_memory_db: Session,
    holdings_with_variants: list[HoldingView],
    monkeypatch: pytest.MonkeyPatch,
    capture_logs: list[tuple[str, str, str, dict | None]],
):
    dummy_compute = _build_dummy_compute(holdings_with_variants)
    monkeypatch.setattr(snapshots, "compute_holdings", dummy_compute)

    snapshot = snapshots.run_snapshot(in_memory_db)

    assert snapshot.value_pea_eur == 250.0 + 400.0
    assert snapshot.value_crypto_eur == 1500.0
    assert snapshot.value_total_eur == 250.0 + 400.0 + 1500.0

    holdings = in_memory_db.query(holdings_model.Holding).all()
    assert {holding.portfolio_type for holding in holdings} == {"PEA", "CRYPTO"}


    completed_log = capture_logs[-1]
    assert completed_log[3]["snapshot"]["value_pea_eur"] == snapshot.value_pea_eur
    assert completed_log[3]["snapshot"]["value_crypto_eur"] == snapshot.value_crypto_eur
