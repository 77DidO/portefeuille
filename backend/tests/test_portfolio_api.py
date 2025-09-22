from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import deps
from app.api import portfolio as portfolio_api
from app.models.base import Base
from app.models.transactions import Transaction
from app.services import portfolio


def _make_holding(*, identifier: str, invested: float, pl: float, as_of: datetime) -> SimpleNamespace:
    market_value = invested + pl
    return SimpleNamespace(
        identifier=identifier,
        asset=identifier.split("::")[-1],
        symbol_or_isin=identifier.split("::")[-1],
        quantity=1.0,
        pru_eur=invested,
        invested_eur=invested,
        market_price_eur=market_value,
        market_value_eur=market_value,
        pl_eur=pl,
        pl_pct=pl / invested * 100.0 if invested else 0.0,
        type_portefeuille=identifier.split("::")[0],
        as_of=as_of,
        account_id=None,
    )


def test_holdings_summary_reports_consistent_pnl(monkeypatch: pytest.MonkeyPatch) -> None:
    holdings = [
        _make_holding(
            identifier="PEA::AAA",
            invested=100.0,
            pl=10.0,
            as_of=datetime(2024, 1, 1, tzinfo=timezone.utc),
        ),
        _make_holding(
            identifier="CTO::BBB",
            invested=200.0,
            pl=20.0,
            as_of=datetime(2024, 1, 1, tzinfo=timezone.utc),
        ),
    ]

    totals = {"latent_pnl": 999.0, "realized_pnl": -999.0}

    def fake_compute_holdings(db):
        return holdings, totals

    monkeypatch.setattr(portfolio_api, "compute_holdings", fake_compute_holdings)

    app = FastAPI()
    app.include_router(portfolio_api.router)
    app.dependency_overrides[deps.get_db] = lambda: None

    client = TestClient(app)
    response = client.get("/portfolio/holdings")
    assert response.status_code == 200

    payload = response.json()
    summary = payload["summary"]

    expected_total_invested = sum(h.invested_eur for h in holdings)
    expected_total_value = sum(h.market_value_eur for h in holdings)
    expected_pl = expected_total_value - expected_total_invested
    expected_pct = sum(h.pl_eur for h in holdings) / expected_total_invested * 100.0

    assert summary["total_invested_eur"] == pytest.approx(expected_total_invested)
    assert summary["total_value_eur"] == pytest.approx(expected_total_value)
    assert summary["pnl_eur"] == pytest.approx(expected_pl)
    assert summary["pnl_eur"] == pytest.approx(summary["total_value_eur"] - summary["total_invested_eur"])
    assert summary["pnl_eur"] == pytest.approx(summary["total_invested_eur"] * summary["pnl_pct"] / 100.0)
    assert summary["pnl_pct"] == pytest.approx(expected_pct)


def _create_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine)
    return engine, TestingSessionLocal


def test_history_endpoint_derives_fifo_points(monkeypatch: pytest.MonkeyPatch) -> None:
    engine, SessionLocal = _create_session()
    db = SessionLocal()
    try:
        portfolio.compute_holdings.cache_clear()

        tx1_ts = datetime(2024, 1, 1, tzinfo=timezone.utc)
        tx2_ts = datetime(2024, 1, 10, tzinfo=timezone.utc)
        tx3_ts = datetime(2024, 2, 1, tzinfo=timezone.utc)

        db.add_all(
            [
                Transaction(
                    account_id="ACC-456",
                    source="TEST",
                    type_portefeuille="PEA",
                    operation="BUY",
                    asset="MSFT",
                    symbol_or_isin="MSFT",
                    quantity=1.0,
                    unit_price_eur=100.0,
                    fee_eur=1.0,
                    total_eur=100.0,
                    ts=tx1_ts,
                    notes=None,
                    external_ref="tx-1",
                ),
                Transaction(
                    account_id="ACC-456",
                    source="TEST",
                    type_portefeuille="PEA",
                    operation="BUY",
                    asset="MSFT",
                    symbol_or_isin="MSFT",
                    quantity=1.0,
                    unit_price_eur=110.0,
                    fee_eur=1.0,
                    total_eur=110.0,
                    ts=tx2_ts,
                    notes=None,
                    external_ref="tx-2",
                ),
                Transaction(
                    account_id="ACC-456",
                    source="TEST",
                    type_portefeuille="PEA",
                    operation="SELL",
                    asset="MSFT",
                    symbol_or_isin="MSFT",
                    quantity=0.5,
                    unit_price_eur=120.0,
                    fee_eur=0.5,
                    total_eur=60.0,
                    ts=tx3_ts,
                    notes=None,
                    external_ref="tx-3",
                ),
            ]
        )
        db.commit()

        def override_get_db():
            session = SessionLocal()
            try:
                yield session
            finally:
                session.close()

        app = FastAPI()
        app.include_router(portfolio_api.router)
        app.dependency_overrides[deps.get_db] = override_get_db

        def fake_get_market_price(symbol: str, type_portefeuille: str | None) -> float:
            return 130.0

        monkeypatch.setattr(portfolio, "get_market_price", fake_get_market_price)

        client = TestClient(app)

        holdings_response = client.get("/portfolio/holdings")
        assert holdings_response.status_code == 200
        holdings_payload = holdings_response.json()["holdings"]
        assert len(holdings_payload) == 1
        identifier = holdings_payload[0]["identifier"]

        detail_response = client.get(f"/portfolio/holdings/{identifier}")
        assert detail_response.status_code == 200
        payload = detail_response.json()
        history = payload["history"]

        assert payload["history_available"] is True
        assert [point["operation"] for point in history] == ["BUY", "BUY", "SELL"]

        def parse_ts(value: str) -> datetime:
            parsed = datetime.fromisoformat(value)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed

        assert [parse_ts(point["ts"]) for point in history] == [tx1_ts, tx2_ts, tx3_ts]

        assert history[0]["quantity"] == pytest.approx(1.0)
        assert history[0]["invested_eur"] == pytest.approx(101.0)
        assert history[0]["pl_eur"] == pytest.approx(-1.0)

        assert history[1]["quantity"] == pytest.approx(2.0)
        assert history[1]["invested_eur"] == pytest.approx(212.0)
        assert history[1]["pl_eur"] == pytest.approx(8.0)

        assert history[2]["quantity"] == pytest.approx(1.5)
        assert history[2]["invested_eur"] == pytest.approx(161.5)
        assert history[2]["pl_eur"] == pytest.approx(18.5)
    finally:
        portfolio.compute_holdings.cache_clear()
        db.close()
        engine.dispose()


def test_history_endpoint_includes_dividends(monkeypatch: pytest.MonkeyPatch) -> None:
    engine, SessionLocal = _create_session()
    db = SessionLocal()
    try:
        portfolio.compute_holdings.cache_clear()

        transactions = [
            Transaction(
                account_id="ACC-789",
                source="TEST",
                type_portefeuille="PEA",
                operation="BUY",
                asset="T",
                symbol_or_isin="T",
                quantity=2.0,
                unit_price_eur=50.0,
                fee_eur=0.0,
                total_eur=100.0,
                ts=datetime(2024, 1, 5, tzinfo=timezone.utc),
                notes=None,
                external_ref="tx-1",
            ),
            Transaction(
                account_id="ACC-789",
                source="TEST",
                type_portefeuille="PEA",
                operation="DIVIDEND",
                asset="T",
                symbol_or_isin="T",
                quantity=0.0,
                unit_price_eur=0.0,
                fee_eur=0.0,
                total_eur=10.0,
                ts=datetime(2024, 2, 1, tzinfo=timezone.utc),
                notes=None,
                external_ref="tx-2",
            ),
        ]

        db.add_all(transactions)
        db.commit()

        def override_get_db():
            session = SessionLocal()
            try:
                yield session
            finally:
                session.close()

        app = FastAPI()
        app.include_router(portfolio_api.router)
        app.dependency_overrides[deps.get_db] = override_get_db

        def fake_get_market_price(symbol: str, type_portefeuille: str | None) -> float:
            return 55.0

        monkeypatch.setattr(portfolio, "get_market_price", fake_get_market_price)

        client = TestClient(app)

        holdings_response = client.get("/portfolio/holdings")
        assert holdings_response.status_code == 200
        holdings_payload = holdings_response.json()["holdings"]
        assert len(holdings_payload) == 1
        identifier = holdings_payload[0]["identifier"]

        detail_response = client.get(f"/portfolio/holdings/{identifier}")
        assert detail_response.status_code == 200
        payload = detail_response.json()
        history = payload["history"]

        assert [point["operation"] for point in history] == ["BUY", "DIVIDEND"]
        assert history[1]["quantity"] == pytest.approx(2.0)
        assert history[1]["invested_eur"] == pytest.approx(100.0)
        assert payload["dividends_eur"] == pytest.approx(10.0)
        assert payload["realized_pnl_eur"] == pytest.approx(10.0)
    finally:
        portfolio.compute_holdings.cache_clear()
        db.close()
        engine.dispose()
