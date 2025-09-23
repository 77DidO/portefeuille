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
    portfolio_type: str,
    operation: str,
    symbol: str,
    quantity: float,
    unit_price: float,
    total: float,
    trade_date: datetime,
    transaction_uid: str,
) -> None:
    tx = Transaction(
        account_id=account_id,
        source="TEST",
        portfolio_type=portfolio_type,
        operation=operation,
        asset=symbol,
        symbol_or_isin=symbol,
        quantity=quantity,
        unit_price_eur=unit_price,
        fee_eur=0.0,
        total_eur=total,
        trade_date=trade_date,
        notes=None,
        transaction_uid=transaction_uid,
    )
    db.add(tx)


def _clear_portfolio_caches():
    portfolio._price_cache.clear()
    portfolio.compute_holdings.cache_clear()


def test_get_market_price_uses_euronext_lookup(monkeypatch):
    _clear_portfolio_caches()
    portfolio.clear_quote_alias_cache()

    search_calls: list[str] = []

    def fake_yahoo_search(isin: str) -> str | None:
        search_calls.append(isin)
        return None

    lookup_calls: list[str] = []

    def fake_lookup(isin: str) -> tuple[str, str]:
        lookup_calls.append(isin)
        return "MC", "XPAR"

    def fake_euronext_search(isin: str) -> tuple[str, str]:
        raise portfolio.euronext.EuronextAPIError("search failed")

    fetch_calls: list[str] = []

    def fake_fetch(issue: str) -> float:
        fetch_calls.append(issue)
        assert issue == "MC-FR0000123456-XPAR"
        return 123.45

    def fail_yahoo(symbol: str) -> float:
        raise AssertionError("Yahoo lookup should not be used when Euronext lookup succeeds")

    monkeypatch.setattr(portfolio, "_search_symbol_for_isin", fake_yahoo_search)
    monkeypatch.setattr(portfolio.euronext, "search_instrument_by_isin", fake_euronext_search)
    monkeypatch.setattr(portfolio.euronext, "lookup_instrument_by_isin", fake_lookup)
    monkeypatch.setattr(portfolio.euronext, "fetch_price", fake_fetch)
    monkeypatch.setattr(portfolio, "_fetch_equity_price", fail_yahoo)

    def fake_load_aliases() -> dict[str, str]:
        try:
            return portfolio._quote_alias_cache[portfolio._QUOTE_ALIAS_CACHE_KEY]
        except KeyError:
            return {}

    monkeypatch.setattr(portfolio, "_load_quote_aliases", fake_load_aliases)

    price = portfolio.get_market_price("FR0000123456", "PEA")

    assert price == pytest.approx(123.45)
    assert search_calls == ["FR0000123456"]
    assert lookup_calls == ["FR0000123456"]
    assert fetch_calls == ["MC-FR0000123456-XPAR"]

    engine, db = _create_session()
    try:
        _add_transaction(
            db,
            account_id=None,
            portfolio_type="PEA",
            operation="BUY",
            symbol="FR0000123456",
            quantity=2.0,
            unit_price=100.0,
            total=200.0,
            trade_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
            transaction_uid="buy",
        )
        db.commit()

        holdings, _ = portfolio.compute_holdings(db)

        assert len(holdings) == 1
        holding = holdings[0]
        assert holding.market_price_eur == pytest.approx(123.45)
        assert holding.market_price_eur != pytest.approx(holding.invested_eur / holding.quantity)
    finally:
        db.close()
        engine.dispose()
        portfolio.clear_quote_alias_cache()


def test_get_market_price_uses_euronext_search(monkeypatch):
    _clear_portfolio_caches()
    portfolio.clear_quote_alias_cache()

    yahoo_search_calls: list[str] = []

    def failing_yahoo_search(isin: str) -> str | None:
        yahoo_search_calls.append(isin)
        return None

    euronext_search_calls: list[str] = []

    def fake_euronext_search(isin: str) -> tuple[str, str]:
        euronext_search_calls.append(isin)
        return "MC", "XPAR"

    def fail_lookup(isin: str) -> tuple[str, str]:
        raise portfolio.euronext.EuronextAPIError("lookup should not be used")

    fetch_calls: list[str] = []

    def fake_fetch(issue: str) -> float:
        fetch_calls.append(issue)
        assert issue == "MC-FR0000123456-XPAR"
        return 321.0

    def fail_yahoo(symbol: str) -> float:
        raise AssertionError("Yahoo lookup should not be used when Euronext search succeeds")

    monkeypatch.setattr(portfolio, "_search_symbol_for_isin", failing_yahoo_search)
    monkeypatch.setattr(portfolio.euronext, "search_instrument_by_isin", fake_euronext_search)
    monkeypatch.setattr(portfolio.euronext, "lookup_instrument_by_isin", fail_lookup)
    monkeypatch.setattr(portfolio.euronext, "fetch_price", fake_fetch)
    monkeypatch.setattr(portfolio, "_fetch_equity_price", fail_yahoo)

    def fake_load_aliases() -> dict[str, str]:
        try:
            return portfolio._quote_alias_cache[portfolio._QUOTE_ALIAS_CACHE_KEY]
        except KeyError:
            return {}

    monkeypatch.setattr(portfolio, "_load_quote_aliases", fake_load_aliases)

    price = portfolio.get_market_price("FR0000123456", "PEA")

    assert price == pytest.approx(321.0)
    assert yahoo_search_calls == ["FR0000123456"]
    assert euronext_search_calls == ["FR0000123456"]
    assert fetch_calls == ["MC-FR0000123456-XPAR"]

    engine, db = _create_session()
    try:
        _add_transaction(
            db,
            account_id=None,
            portfolio_type="PEA",
            operation="BUY",
            symbol="FR0000123456",
            quantity=3.0,
            unit_price=100.0,
            total=300.0,
            trade_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
            transaction_uid="buy",
        )
        db.commit()

        holdings, _ = portfolio.compute_holdings(db)

        assert len(holdings) == 1
        holding = holdings[0]
        assert holding.market_price_eur == pytest.approx(321.0)
        assert holding.market_value_eur == pytest.approx(963.0)
    finally:
        db.close()
        engine.dispose()
        portfolio.clear_quote_alias_cache()


def test_get_market_price_uses_euronext_symbol_lookup(monkeypatch):
    _clear_portfolio_caches()
    portfolio.clear_quote_alias_cache()

    search_calls: list[tuple[str, str | None]] = []

    def fake_symbol_search(symbol: str, mic: str | None) -> tuple[str, str]:
        search_calls.append((symbol, mic))
        return "FR0000123456", "XPAR"

    fetch_calls: list[str] = []

    def fake_fetch(issue: str) -> float:
        fetch_calls.append(issue)
        assert issue == "MC-FR0000123456-XPAR"
        return 654.32

    def fail_equity(symbol: str) -> float:
        raise AssertionError("Equity fallback should not be used when Euronext symbol search succeeds")

    monkeypatch.setattr(portfolio.euronext, "search_instrument_by_symbol", fake_symbol_search)
    monkeypatch.setattr(portfolio.euronext, "fetch_price", fake_fetch)
    monkeypatch.setattr(portfolio, "_fetch_equity_price", fail_equity)

    def fake_load_aliases() -> dict[str, str]:
        try:
            return portfolio._quote_alias_cache[portfolio._QUOTE_ALIAS_CACHE_KEY]
        except KeyError:
            return {}

    monkeypatch.setattr(portfolio, "_load_quote_aliases", fake_load_aliases)

    price = portfolio.get_market_price("MC.PA", "PEA")

    assert price == pytest.approx(654.32)
    assert search_calls == [("MC", "XPAR")]
    assert fetch_calls == ["MC-FR0000123456-XPAR"]


def test_get_market_price_prefers_euronext(monkeypatch):
    _clear_portfolio_caches()

    resolved_calls: list[tuple[str, str | None]] = []

    def fake_resolve(symbol: str, portfolio_type: str | None) -> str:
        resolved_calls.append((symbol, portfolio_type))
        return "MC.PA"

    fetch_calls: list[str] = []

    def fake_fetch(issue: str) -> float:
        fetch_calls.append(issue)
        assert issue == "MC-FR0000123456-XPAR"
        return 42.0

    def fail_yahoo(symbol: str) -> float:
        raise AssertionError("Yahoo fetch should not be used when Euronext succeeds")

    monkeypatch.setattr(portfolio, "resolve_quote_symbol", fake_resolve)
    monkeypatch.setattr(portfolio.euronext, "fetch_price", fake_fetch)
    monkeypatch.setattr(portfolio, "_fetch_equity_price", fail_yahoo)

    price = portfolio.get_market_price("FR0000123456", "PEA")

    assert price == pytest.approx(42.0)
    assert resolved_calls == [("FR0000123456", "PEA")]
    assert fetch_calls == ["MC-FR0000123456-XPAR"]


def test_get_market_price_falls_back_to_yahoo(monkeypatch):
    _clear_portfolio_caches()

    def fake_resolve(symbol: str, portfolio_type: str | None) -> str:
        return "MC.PA"

    fetch_calls: list[str] = []

    def failing_fetch(issue: str) -> float:
        fetch_calls.append(issue)
        assert issue == "MC-FR0000123456-XPAR"
        raise portfolio.euronext.EuronextAPIError("boom")

    yahoo_calls: list[str] = []

    def fake_yahoo(symbol: str) -> float:
        yahoo_calls.append(symbol)
        return 84.0

    monkeypatch.setattr(portfolio, "resolve_quote_symbol", fake_resolve)
    monkeypatch.setattr(portfolio.euronext, "fetch_price", failing_fetch)
    monkeypatch.setattr(portfolio, "_fetch_equity_price", fake_yahoo)

    price = portfolio.get_market_price("FR0000123456", "CTO")

    assert price == pytest.approx(84.0)
    assert fetch_calls == ["MC-FR0000123456-XPAR"]
    assert yahoo_calls == ["MC.PA"]


def test_get_market_price_falls_back_to_yahoo_with_isin(monkeypatch):
    _clear_portfolio_caches()
    portfolio.clear_quote_alias_cache()

    def fake_resolve(symbol: str, portfolio_type: str | None) -> str:
        return "FR0000123456"

    def fake_iter(original: str, resolved: str) -> tuple[str, ...]:
        return ("MC-FR0000123456-XPAR",)

    euronext_calls: list[str] = []

    def failing_fetch(issue: str) -> float:
        euronext_calls.append(issue)
        raise portfolio.euronext.EuronextAPIError("boom")

    search_calls: list[str] = []

    def fake_search(isin: str) -> str | None:
        search_calls.append(isin)
        return "MC.PA"

    yahoo_calls: list[str] = []

    def fake_yahoo(symbol: str) -> float:
        yahoo_calls.append(symbol)
        return 91.0

    monkeypatch.setattr(portfolio, "resolve_quote_symbol", fake_resolve)
    monkeypatch.setattr(portfolio, "_iter_euronext_candidates", fake_iter)
    monkeypatch.setattr(portfolio.euronext, "fetch_price", failing_fetch)
    monkeypatch.setattr(portfolio, "_search_symbol_for_isin", fake_search)
    monkeypatch.setattr(portfolio, "_fetch_equity_price", fake_yahoo)

    price = portfolio.get_market_price("FR0000123456", "PEA")

    assert price == pytest.approx(91.0)
    assert euronext_calls == ["MC-FR0000123456-XPAR"]
    assert search_calls == ["FR0000123456"]
    assert yahoo_calls == ["MC.PA"]


def test_get_market_price_adjusts_yahoo_symbol_for_isin(monkeypatch):
    _clear_portfolio_caches()
    portfolio.clear_quote_alias_cache()

    def fake_resolve(symbol: str, portfolio_type: str | None) -> str:
        return "FR0000123456"

    def fake_iter(original: str, resolved: str) -> tuple[str, ...]:
        return ("MC-FR0000123456-XPAR",)

    def failing_fetch(issue: str) -> float:
        raise portfolio.euronext.EuronextAPIError("boom")

    search_calls: list[str] = []

    def fake_search(isin: str) -> str | None:
        search_calls.append(isin)
        return "MC.PA"

    yahoo_calls: list[str] = []

    def fake_yahoo(symbol: str) -> float:
        yahoo_calls.append(symbol)
        assert symbol == "MC.PA"
        return 109.0

    def identity_derive(symbol: str) -> str:
        return symbol

    monkeypatch.setattr(portfolio, "resolve_quote_symbol", fake_resolve)
    monkeypatch.setattr(portfolio, "_iter_euronext_candidates", fake_iter)
    monkeypatch.setattr(portfolio.euronext, "fetch_price", failing_fetch)
    monkeypatch.setattr(portfolio, "_search_symbol_for_isin", fake_search)
    monkeypatch.setattr(portfolio, "_fetch_equity_price", fake_yahoo)
    monkeypatch.setattr(portfolio, "_derive_equity_fetch_symbol", identity_derive)

    price = portfolio.get_market_price("FR0000123456", "CTO")

    assert price == pytest.approx(109.0)
    assert search_calls == ["FR0000123456"]
    assert yahoo_calls == ["MC.PA"]


@pytest.mark.parametrize("account_ids", [(None, None), ("ACC-PEA", "ACC-CTO")])
def test_compute_holdings_separates_same_symbol(monkeypatch, account_ids):
    engine, db = _create_session()
    try:
        portfolio.compute_holdings.cache_clear()

        account_pea, account_cto = account_ids
        _add_transaction(
            db,
            account_id=account_pea,
            portfolio_type="PEA",
            operation="BUY",
            symbol="AAPL",
            quantity=10.0,
            unit_price=100.0,
            total=1000.0,
            trade_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
            transaction_uid="pea-buy",
        )
        _add_transaction(
            db,
            account_id=account_cto,
            portfolio_type="CTO",
            operation="BUY",
            symbol="AAPL",
            quantity=5.0,
            unit_price=110.0,
            total=550.0,
            trade_date=datetime(2024, 1, 2, tzinfo=timezone.utc),
            transaction_uid="cto-buy",
        )
        db.commit()

        prices = {
            ("AAPL", "PEA"): 120.0,
            ("AAPL", "CTO"): 150.0,
        }

        def fake_get_market_price(symbol: str, portfolio_type: str | None) -> float:
            key = (symbol, (portfolio_type or "").upper())
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
