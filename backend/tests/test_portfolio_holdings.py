from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.transactions import Transaction
from app.services.portfolio import _cache, compute_holdings


def setup_db(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path}/holdings.db", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, autocommit=False, autoflush=False)


def test_compute_holdings_handles_fiat_sell(tmp_path):
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
        holdings, totals = compute_holdings(db)

        assert any(h.asset == "ACME" for h in holdings)
        assert totals["realized_pnl"] == pytest.approx(250.0)
    finally:
        db.close()
