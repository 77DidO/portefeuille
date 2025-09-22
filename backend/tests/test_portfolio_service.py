from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.transactions import Transaction
from app.services import portfolio


def _create_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine)
    db = TestingSessionLocal()
    return engine, db


def _add_transaction(
    db,
    *,
    account_id: str | None,
    type_portefeuille: str,
    operation: str,
    symbol: str,
    quantity: float,
    unit_price: float,
    total: float,
    ts: datetime,
    external_ref: str,
) -> None:
    tx = Transaction(
        account_id=account_id,
        source="TEST",
        type_portefeuille=type_portefeuille,
        operation=operation,
        asset=symbol,
        symbol_or_isin=symbol,
        quantity=quantity,
        unit_price_eur=unit_price,
        fee_eur=0.0,
        total_eur=total,
        ts=ts,
        notes=None,
        external_ref=external_ref,
    )
    db.add(tx)


@pytest.mark.parametrize("account_ids", [(None, None), ("ACC-PEA", "ACC-CTO")])
def test_compute_holdings_separates_same_symbol(monkeypatch, account_ids):
    engine, db = _create_session()
    try:
        portfolio.compute_holdings.cache_clear()

        account_pea, account_cto = account_ids
        _add_transaction(
            db,
            account_id=account_pea,
            type_portefeuille="PEA",
            operation="BUY",
            symbol="AAPL",
            quantity=10.0,
            unit_price=100.0,
            total=1000.0,
            ts=datetime(2024, 1, 1, tzinfo=timezone.utc),
            external_ref="pea-buy",
        )
        _add_transaction(
            db,
            account_id=account_cto,
            type_portefeuille="CTO",
            operation="BUY",
            symbol="AAPL",
            quantity=5.0,
            unit_price=110.0,
            total=550.0,
            ts=datetime(2024, 1, 2, tzinfo=timezone.utc),
            external_ref="cto-buy",
        )
        db.commit()

        prices = {
            ("AAPL", "PEA"): 120.0,
            ("AAPL", "CTO"): 150.0,
        }

        def fake_get_market_price(symbol: str, type_portefeuille: str | None) -> float:
            key = (symbol, (type_portefeuille or "").upper())
            if key not in prices:
                raise AssertionError(f"unexpected price lookup: {key}")
            return prices[key]

        monkeypatch.setattr(portfolio, "get_market_price", fake_get_market_price)

        holdings, totals = portfolio.compute_holdings(db)

        assert len(holdings) == 2
        pea_holding = next(h for h in holdings if h.type_portefeuille == "PEA")
        cto_holding = next(h for h in holdings if h.type_portefeuille == "CTO")

        assert pea_holding.symbol_or_isin == "AAPL"
        assert cto_holding.symbol_or_isin == "AAPL"
        assert pea_holding.identifier != cto_holding.identifier

        assert pea_holding.quantity == pytest.approx(10.0)
        assert pea_holding.invested_eur == pytest.approx(1000.0)
        assert pea_holding.market_value_eur == pytest.approx(1200.0)
        assert pea_holding.pl_eur == pytest.approx(200.0)

        assert cto_holding.quantity == pytest.approx(5.0)
        assert cto_holding.invested_eur == pytest.approx(550.0)
        assert cto_holding.market_value_eur == pytest.approx(750.0)
        assert cto_holding.pl_eur == pytest.approx(200.0)

        assert totals["total_value"] == pytest.approx(1950.0)
        assert totals["total_invested"] == pytest.approx(1550.0)

        if account_pea:
            assert pea_holding.account_id == account_pea
        else:
            assert pea_holding.account_id is None
        if account_cto:
            assert cto_holding.account_id == account_cto
        else:
            assert cto_holding.account_id is None

        detail_pea = portfolio.compute_holding_detail(db, pea_holding.identifier)
        detail_cto = portfolio.compute_holding_detail(db, cto_holding.identifier)

        assert detail_pea.quantity == pytest.approx(10.0)
        assert detail_cto.quantity == pytest.approx(5.0)
        assert detail_pea.identifier != detail_cto.identifier

    finally:
        db.close()
        engine.dispose()
