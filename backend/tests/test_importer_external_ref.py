from __future__ import annotations

import textwrap

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.base import Base
from app.models.transactions import Transaction
from app.services.importer import Importer, compute_external_ref_from_row


def _create_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine)
    return engine, TestingSessionLocal


def test_compute_external_ref_normalizes_numeric_values() -> None:
    row_a = {
        "source": "BROKER_A",
        "type_portefeuille": "CTO",
        "operation": "BUY",
        "asset": "ASSET-1",
        "symbol_or_isin": "AAA",
        "quantity": "1",
        "unit_price_eur": "100",
        "fee_eur": "",
        "fee_asset": "USD",
        "fx_rate": "",
        "total_eur": "100",
        "ts": "2024-01-01T12:00:00+00:00",
        "notes": "",
        "external_ref": "",
    }
    row_b = {
        **row_a,
        "quantity": "1.000",
        "unit_price_eur": "100.00",
        "fee_eur": "0.0000",
        "fx_rate": "1",
        "total_eur": "100.000",
    }

    assert compute_external_ref_from_row(row_a) == compute_external_ref_from_row(row_b)


def test_importer_does_not_duplicate_permuted_rows() -> None:
    engine, SessionLocal = _create_session()
    db = SessionLocal()
    try:
        importer = Importer(db)
        header = (
            "source,type_portefeuille,operation,asset,symbol_or_isin,quantity,unit_price_eur," +
            "fee_eur,fee_asset,fx_rate,total_eur,ts,notes,external_ref\n"
        )
        row_a = "BROKER_A,CTO,BUY,ASSET-1,AAA,1,100,0,USD,,100,2024-01-01T12:00:00+00:00,,\n"
        row_b = "BROKER_B,CTO,SELL,ASSET-2,BBB,2,50,0,,0.95,100,2024-01-02T12:00:00+00:00,,\n"

        importer.import_transactions_csv(header + row_a + row_b)
        first_transactions = {
            (t.source, t.operation, t.asset, t.ts.isoformat()): t.external_ref
            for t in db.query(Transaction).all()
        }

        importer.import_transactions_csv(header + row_b + row_a)
        updated_transactions = db.query(Transaction).all()
        assert len(updated_transactions) == 2

        for transaction in updated_transactions:
            key = (transaction.source, transaction.operation, transaction.asset, transaction.ts.isoformat())
            assert first_transactions[key] == transaction.external_ref

        expected_rows = textwrap.dedent(
            """
            source,type_portefeuille,operation,asset,symbol_or_isin,quantity,unit_price_eur,fee_eur,fee_asset,fx_rate,total_eur,ts,notes,external_ref
            BROKER_A,CTO,BUY,ASSET-1,AAA,1,100,0,USD,,100,2024-01-01T12:00:00+00:00,,
            BROKER_B,CTO,SELL,ASSET-2,BBB,2,50,0,,0.95,100,2024-01-02T12:00:00+00:00,,
            """
        ).strip().splitlines()[1:]
        for csv_line, transaction in zip(expected_rows, sorted(updated_transactions, key=lambda t: t.ts)):
            row_values = dict(zip(header.strip().split(","), csv_line.split(",")))
            assert transaction.external_ref == compute_external_ref_from_row(row_values)
    finally:
        db.close()
        engine.dispose()
