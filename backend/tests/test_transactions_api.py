from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import deps
from app.api import transactions as transactions_api
from app.models.base import Base
from app.models.transactions import Transaction


def _create_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine)
    return engine, TestingSessionLocal


def test_list_transactions_supports_filters() -> None:
    engine, SessionLocal = _create_session()
    db = SessionLocal()
    try:
        base_ts = datetime(2024, 1, 1, tzinfo=timezone.utc)

        db.add_all(
            [
                Transaction(
                    account_id="ACC-1",
                    source="BROKER_A",
                    portfolio_type="PEA",
                    operation="BUY",
                    asset="ASSET-1",
                    symbol_or_isin="ASSET-1",
                    quantity=1.0,
                    unit_price_eur=100.0,
                    fee_eur=1.0,
                    total_eur=100.0,
                    trade_date=base_ts,
                    notes=None,
                    transaction_uid="tx-1",
                ),
                Transaction(
                    account_id="ACC-1",
                    source="BROKER_B",
                    portfolio_type="PEA",
                    operation="BUY",
                    asset="ASSET-2",
                    symbol_or_isin="ASSET-2",
                    quantity=1.0,
                    unit_price_eur=110.0,
                    fee_eur=1.0,
                    total_eur=110.0,
                    trade_date=base_ts + timedelta(days=1),
                    notes=None,
                    transaction_uid="tx-2",
                ),
                Transaction(
                    account_id="ACC-1",
                    source="BROKER_A",
                    portfolio_type="CTO",
                    operation="BUY",
                    asset="ASSET-3",
                    symbol_or_isin="ASSET-3",
                    quantity=1.0,
                    unit_price_eur=120.0,
                    fee_eur=1.0,
                    total_eur=120.0,
                    trade_date=base_ts + timedelta(days=2),
                    notes=None,
                    transaction_uid="tx-3",
                ),
                Transaction(
                    account_id="ACC-2",
                    source="BROKER_B",
                    portfolio_type="CTO",
                    operation="SELL",
                    asset="ASSET-1",
                    symbol_or_isin="ASSET-1",
                    quantity=0.5,
                    unit_price_eur=130.0,
                    fee_eur=1.0,
                    total_eur=65.0,
                    trade_date=base_ts + timedelta(days=3),
                    notes=None,
                    transaction_uid="tx-4",
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
        app.include_router(transactions_api.router)
        app.dependency_overrides[deps.get_db] = override_get_db

        client = TestClient(app)

        response = client.get("/transactions/")
        assert response.status_code == 200
        payload = response.json()
        assert [item["transaction_uid"] for item in payload] == [
            "tx-4",
            "tx-3",
            "tx-2",
            "tx-1",
        ]

        response = client.get("/transactions/", params={"source": "BROKER_A"})
        assert response.status_code == 200
        payload = response.json()
        assert [item["transaction_uid"] for item in payload] == ["tx-3", "tx-1"]

        response = client.get("/transactions/", params={"type": "PEA"})
        assert response.status_code == 200
        payload = response.json()
        assert [item["transaction_uid"] for item in payload] == ["tx-2", "tx-1"]

        response = client.get("/transactions/", params={"asset": "ASSET-1"})
        assert response.status_code == 200
        payload = response.json()
        assert [item["transaction_uid"] for item in payload] == ["tx-4", "tx-1"]

        response = client.get("/transactions/", params={"operation": "SELL"})
        assert response.status_code == 200
        payload = response.json()
        assert [item["transaction_uid"] for item in payload] == ["tx-4"]

    finally:
        db.close()
        engine.dispose()
