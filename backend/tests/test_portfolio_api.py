from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import deps
from app.api import portfolio as portfolio_api


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
