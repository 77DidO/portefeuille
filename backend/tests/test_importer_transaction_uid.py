from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.base import Base
from app.models.transactions import Transaction
from app.services.importer import Importer, compute_transaction_uid_from_row


def _create_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine)
    return engine, TestingSessionLocal


def test_compute_transaction_uid_normalizes_numeric_values() -> None:
    row_a = {
        "id": "",
        "source": "BROKER_A",
        "portfolio_type": "CTO",
        "operation": "BUY",
        "date": "2024-01-01T12:00:00+00:00",
        "asset": "ASSET-1",
        "symbol": "AAA",
        "isin": "",
        "mic": "",
        "quantity": "1",
        "unit_price_eur": "100",
        "total_eur": "100",
        "fee_eur": "",
        "fee_asset": "USD",
        "fee_quantity": "0",
        "notes": "",
    }
    row_b = {
        **row_a,
        "quantity": "1.000",
        "unit_price_eur": "100.00",
        "fee_eur": "0.0000",
        "total_eur": "100.000",
        "fee_quantity": "0.000",
    }

    assert compute_transaction_uid_from_row(row_a) == compute_transaction_uid_from_row(row_b)


def test_compute_transaction_uid_prefers_id() -> None:
    row = {
        "id": "tx-1",
        "source": "BROKER_A",
        "portfolio_type": "CTO",
        "operation": "BUY",
        "date": "2024-01-01T12:00:00+00:00",
        "asset": "ASSET-1",
        "symbol": "AAA",
        "isin": "",
        "mic": "",
        "quantity": "1",
        "unit_price_eur": "100",
        "total_eur": "100",
        "fee_eur": "0.0000",
        "fee_asset": "",
        "fee_quantity": "",
        "notes": "",
    }

    assert compute_transaction_uid_from_row(row) == "tx-1"


def test_importer_does_not_duplicate_permuted_rows() -> None:
    engine, SessionLocal = _create_session()
    db = SessionLocal()
    try:
        importer = Importer(db)
        header = (
            "id,source,portfolio_type,operation,date,asset,symbol,isin,mic,quantity,unit_price_eur,total_eur,"
            "fee_eur,fee_asset,fee_quantity,notes\n"
        )
        row_a = (
            "tx-1,BROKER_A,CTO,BUY,2024-01-01T12:00:00+00:00,ASSET-1,AAA,,,1,100,100,0,USD,,\n"
        )
        row_b = (
            "tx-2,BROKER_B,CTO,SELL,2024-01-02T12:00:00+00:00,ASSET-2,BBB,,,2,50,100,0,,,\n"
        )

        importer.import_transactions_csv(header + row_a + row_b)
        first_transactions = {
            (t.source, t.operation, t.asset, t.trade_date.isoformat()): t.transaction_uid
            for t in db.query(Transaction).all()
        }

        importer.import_transactions_csv(header + row_b + row_a)
        updated_transactions = db.query(Transaction).all()
        assert len(updated_transactions) == 2

        for transaction in updated_transactions:
            key = (
                transaction.source,
                transaction.operation,
                transaction.asset,
                transaction.trade_date.isoformat(),
            )
            assert first_transactions[key] == transaction.transaction_uid

        for transaction in updated_transactions:
            assert transaction.transaction_uid in {"tx-1", "tx-2"}
    finally:
        db.close()
        engine.dispose()
