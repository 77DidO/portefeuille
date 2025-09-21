from __future__ import annotations

from datetime import datetime, timezone
import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.transactions import Transaction
from app.models.holdings import Holding
from app.models.settings import Setting
import httpx

from app.services.portfolio import (
    _cache,
    _price_cache,
    clear_quote_alias_cache,
    compute_holding_detail,
    compute_holdings,
    HoldingNotFound,
)
from app.utils.settings_keys import QUOTE_ALIAS_SETTING_KEY


def setup_db(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path}/holdings.db", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, autocommit=False, autoflush=False)


def test_compute_holdings_handles_fiat_sell(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.services.portfolio.get_market_price", lambda symbol, type_portefeuille=None: 100.0
    )
    Session = setup_db(tmp_path)
    db = Session()
    try:
        db.add_all(
            [
                Transaction(
                    source="broker",
                    type_portefeuille="CTO",
                    operation="BUY",
                    asset="Acme Corp",
                    symbol_or_isin="ACME",
                    quantity=10.0,
                    unit_price_eur=100.0,
                    fee_eur=0.0,
                    total_eur=1000.0,
                    ts=datetime(2024, 1, 1, tzinfo=timezone.utc),
                    notes="",
                    external_ref="buy-acme",
                ),
                Transaction(
                    source="broker",
                    type_portefeuille="CTO",
                    operation="SELL",
                    asset="Acme Corp",
                    symbol_or_isin="ACME",
                    quantity=5.0,
                    unit_price_eur=120.0,
                    fee_eur=0.0,
                    total_eur=600.0,
                    ts=datetime(2024, 1, 15, tzinfo=timezone.utc),
                    notes="",
                    external_ref="sell-acme",
                ),
                Transaction(
                    source="broker",
                    type_portefeuille="CTO",
                    operation="SELL",
                    asset="USD",
                    symbol_or_isin="",
                    quantity=0.0,
                    unit_price_eur=1.0,
                    fee_eur=0.0,
                    total_eur=150.0,
                    ts=datetime(2024, 1, 20, tzinfo=timezone.utc),
                    notes="",
                    external_ref="cash-withdrawal",
                ),
            ]
        )
        db.commit()

        _cache.clear()
        _price_cache.clear()
        holdings, totals = compute_holdings(db)

        assert any(h.asset == "ACME" for h in holdings)
        assert totals["realized_pnl"] == pytest.approx(250.0)
    finally:
        db.close()


def test_compute_holdings_handles_symbol_only_fiat_sell(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.services.portfolio.get_market_price", lambda symbol, type_portefeuille=None: 100.0
    )
    Session = setup_db(tmp_path)
    db = Session()
    try:
        db.add(
            Transaction(
                source="broker",
                type_portefeuille="CTO",
                operation="SELL",
                asset="Savings Account",
                symbol_or_isin="EUR",
                quantity=0.0,
                unit_price_eur=1.0,
                fee_eur=2.5,
                total_eur=500.0,
                ts=datetime(2024, 2, 1, tzinfo=timezone.utc),
                notes="",
                external_ref="cash-out-eur",
            )
        )
        db.commit()

        _cache.clear()
        _price_cache.clear()
        holdings, totals = compute_holdings(db)

        assert holdings == []
        assert totals["realized_pnl"] == pytest.approx(497.5)
    finally:
        db.close()


def test_compute_holdings_respects_crypto_portfolio_type(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.services.portfolio.get_market_price", lambda symbol, type_portefeuille=None: 100.0
    )
    Session = setup_db(tmp_path)
    db = Session()
    try:
        db.add_all(
            [
                Transaction(
                    source="exchange",
                    type_portefeuille="CRYPTO",
                    operation="BUY",
                    asset="Bitcoin",
                    symbol_or_isin="BTC",
                    quantity=0.5,
                    unit_price_eur=20000.0,
                    fee_eur=10.0,
                    total_eur=10000.0,
                    ts=datetime(2024, 3, 1, tzinfo=timezone.utc),
                    notes="",
                    external_ref="buy-btc",
                ),
                Transaction(
                    source="exchange",
                    type_portefeuille="PEA",
                    operation="BUY",
                    asset="Solana",
                    symbol_or_isin="SOL",
                    quantity=5.0,
                    unit_price_eur=100.0,
                    fee_eur=0.0,
                    total_eur=500.0,
                    ts=datetime(2024, 3, 2, tzinfo=timezone.utc),
                    notes="",
                    external_ref="buy-sol",
                ),
            ]
        )
        db.commit()

        _cache.clear()
        _price_cache.clear()
        holdings, _ = compute_holdings(db)

        crypto_assets = {h.asset for h in holdings if h.type_portefeuille == "CRYPTO"}
        pea_assets = {h.asset for h in holdings if h.type_portefeuille == "PEA"}

        assert crypto_assets == {"BTC"}
        assert "SOL" in pea_assets
    finally:
        db.close()


def test_compute_holdings_resolves_isin_alias(tmp_path, monkeypatch):
    Session = setup_db(tmp_path)
    db = Session()
    try:
        isin = "FR0000120073"
        alias = {isin: "AIR.PA"}
        db.add(
            Setting(
                key=QUOTE_ALIAS_SETTING_KEY,
                value=json.dumps(alias),
                updated_at=datetime(2024, 5, 1, tzinfo=timezone.utc),
            )
        )
        db.add(
            Transaction(
                source="broker",
                type_portefeuille="PEA",
                operation="BUY",
                asset="Air Liquide",
                symbol_or_isin=isin,
                quantity=4.0,
                unit_price_eur=100.0,
                fee_eur=0.0,
                total_eur=400.0,
                ts=datetime(2024, 4, 15, tzinfo=timezone.utc),
                notes="",
                external_ref="buy-air-liquide",
            )
        )
        db.commit()

        monkeypatch.setattr("app.services.portfolio.SessionLocal", Session)

        def fake_http_get(self, url, params):
            assert params.get("symbols") == "AIR.PA"

            class DummyResponse:
                def raise_for_status(self_inner):
                    return None

                def json(self_inner):
                    return {
                        "quoteResponse": {
                            "result": [
                                {
                                    "regularMarketPrice": 180.5,
                                }
                            ]
                        }
                    }

            return DummyResponse()

        monkeypatch.setattr(httpx.Client, "get", fake_http_get, raising=False)

        _cache.clear()
        _price_cache.clear()
        clear_quote_alias_cache()
        holdings, _ = compute_holdings(db)

        assert holdings[0].market_price_eur == pytest.approx(180.5)
        assert holdings[0].market_price_eur != pytest.approx(holdings[0].pru_eur)
    finally:
        db.close()


def test_compute_holdings_uses_market_prices(tmp_path, monkeypatch):
    Session = setup_db(tmp_path)
    db = Session()
    try:
        db.add(
            Transaction(
                source="broker",
                type_portefeuille="CTO",
                operation="BUY",
                asset="Acme Corp",
                symbol_or_isin="ACME",
                quantity=10.0,
                unit_price_eur=100.0,
                fee_eur=0.0,
                total_eur=1000.0,
                ts=datetime(2024, 4, 1, tzinfo=timezone.utc),
                notes="",
                external_ref="buy-acme",
            )
        )
        db.commit()

        def fake_http_get(self, url, params):
            class DummyResponse:
                def raise_for_status(self_inner):
                    return None

                def json(self_inner):
                    return {
                        "quoteResponse": {
                            "result": [
                                {
                                    "regularMarketPrice": 125.5,
                                }
                            ]
                        }
                    }

            return DummyResponse()

        monkeypatch.setattr(httpx.Client, "get", fake_http_get, raising=False)

        _cache.clear()
        _price_cache.clear()
        holdings, totals = compute_holdings(db)

        assert holdings[0].market_price_eur == pytest.approx(125.5)
        assert holdings[0].market_value_eur == pytest.approx(1255.0)
        assert holdings[0].pl_eur == pytest.approx(255.0)
        assert holdings[0].pl_pct == pytest.approx(25.5)
        assert totals["total_value"] == pytest.approx(1255.0)
        assert totals["latent_pnl"] == pytest.approx(255.0)
    finally:
        db.close()


def test_compute_holdings_reuses_cached_price_on_failure(tmp_path, monkeypatch):
    Session = setup_db(tmp_path)
    db = Session()
    try:
        db.add(
            Transaction(
                source="broker",
                type_portefeuille="CTO",
                operation="BUY",
                asset="Acme Corp",
                symbol_or_isin="ACME",
                quantity=2.0,
                unit_price_eur=100.0,
                fee_eur=0.0,
                total_eur=200.0,
                ts=datetime(2024, 4, 10, tzinfo=timezone.utc),
                notes="",
                external_ref="buy-acme-2",
            )
        )
        db.commit()

        def fake_http_success(self, url, params):
            class DummyResponse:
                def raise_for_status(self_inner):
                    return None

                def json(self_inner):
                    return {
                        "quoteResponse": {"result": [{"regularMarketPrice": 150.0}]}
                    }

            return DummyResponse()

        def fake_http_failure(self, url, params):
            raise httpx.ReadTimeout("timeout")

        monkeypatch.setattr(httpx.Client, "get", fake_http_success, raising=False)

        _cache.clear()
        _price_cache.clear()
        holdings, _ = compute_holdings(db)
        assert holdings[0].market_price_eur == pytest.approx(150.0)

        monkeypatch.setattr(httpx.Client, "get", fake_http_failure, raising=False)

        _cache.clear()
        holdings, _ = compute_holdings(db)
        assert holdings[0].market_price_eur == pytest.approx(150.0)
    finally:
        db.close()


def test_compute_holding_detail_returns_history(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.services.portfolio.get_market_price", lambda symbol, type_portefeuille=None: 125.0
    )
    Session = setup_db(tmp_path)
    db = Session()
    try:
        db.add_all(
            [
                Transaction(
                    source="broker",
                    type_portefeuille="CTO",
                    operation="BUY",
                    asset="Acme Corp",
                    symbol_or_isin="ACME",
                    quantity=2.0,
                    unit_price_eur=100.0,
                    fee_eur=0.0,
                    total_eur=200.0,
                    ts=datetime(2024, 1, 1, tzinfo=timezone.utc),
                    notes="",
                    external_ref="buy-acme-1",
                ),
                Transaction(
                    source="broker",
                    type_portefeuille="CTO",
                    operation="SELL",
                    asset="Acme Corp",
                    symbol_or_isin="ACME",
                    quantity=1.0,
                    unit_price_eur=150.0,
                    fee_eur=0.0,
                    total_eur=150.0,
                    ts=datetime(2024, 2, 1, tzinfo=timezone.utc),
                    notes="",
                    external_ref="sell-acme-1",
                ),
                Transaction(
                    source="broker",
                    type_portefeuille="CTO",
                    operation="DIVIDEND",
                    asset="Acme Corp",
                    symbol_or_isin="ACME",
                    quantity=0.0,
                    unit_price_eur=0.0,
                    fee_eur=0.0,
                    total_eur=10.0,
                    ts=datetime(2024, 2, 15, tzinfo=timezone.utc),
                    notes="",
                    external_ref="dividend-acme",
                ),
            ]
        )
        db.add_all(
            [
                Holding(
                    asset="Acme Corp",
                    symbol_or_isin="ACME",
                    quantity=1.0,
                    pru_eur=100.0,
                    invested_eur=100.0,
                    market_price_eur=110.0,
                    market_value_eur=110.0,
                    pl_eur=10.0,
                    pl_pct=10.0,
                    as_of=datetime(2024, 2, 1, tzinfo=timezone.utc),
                ),
                Holding(
                    asset="Acme Corp",
                    symbol_or_isin="ACME",
                    quantity=1.0,
                    pru_eur=100.0,
                    invested_eur=100.0,
                    market_price_eur=125.0,
                    market_value_eur=125.0,
                    pl_eur=25.0,
                    pl_pct=25.0,
                    as_of=datetime(2024, 3, 1, tzinfo=timezone.utc),
                ),
            ]
        )
        db.commit()

        _cache.clear()
        _price_cache.clear()

        detail = compute_holding_detail(db, "ACME")

        assert detail.asset == "ACME"
        assert detail.history_available is True
        assert len(detail.history) == 2
        assert detail.realized_pnl_eur == pytest.approx(60.0)
        assert detail.dividends_eur == pytest.approx(10.0)
    finally:
        db.close()


def test_compute_holding_detail_handles_missing_history(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.services.portfolio.get_market_price", lambda symbol, type_portefeuille=None: 50.0
    )
    Session = setup_db(tmp_path)
    db = Session()
    try:
        db.add(
            Transaction(
                source="broker",
                type_portefeuille="CTO",
                operation="BUY",
                asset="Widget",
                symbol_or_isin="WID",
                quantity=3.0,
                unit_price_eur=40.0,
                fee_eur=0.0,
                total_eur=120.0,
                ts=datetime(2024, 1, 1, tzinfo=timezone.utc),
                notes="",
                external_ref="buy-widget",
            )
        )
        db.commit()

        _cache.clear()
        _price_cache.clear()

        detail = compute_holding_detail(db, "WID")

        assert detail.history == []
        assert detail.history_available is False
    finally:
        db.close()


def test_compute_holding_detail_raises_for_unknown_asset(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.services.portfolio.get_market_price", lambda symbol, type_portefeuille=None: 42.0
    )
    Session = setup_db(tmp_path)
    db = Session()
    try:
        _cache.clear()
        _price_cache.clear()

        with pytest.raises(HoldingNotFound):
            compute_holding_detail(db, "UNKNOWN")
    finally:
        db.close()
