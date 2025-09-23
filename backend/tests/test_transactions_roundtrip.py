from __future__ import annotations

import csv
import io
import zipfile

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import deps
from app.api import transactions as transactions_api
from app.models.base import Base
from app.models.transactions import Transaction
from app.services.exporter import export_zip
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


def test_transactions_roundtrip_preserves_fee_fields() -> None:
    engine, SessionLocal = _create_session()
    db = SessionLocal()
    try:
        importer = Importer(db)
        csv_content = """source,type_portefeuille,operation,asset,symbol_or_isin,quantity,unit_price_eur,fee_eur,fee_asset,fx_rate,total_eur,ts,notes,external_ref\n"""
        csv_content += """BROKER_A,CTO,BUY,ASSET-1,AAA,1.0,100.0,1.0,USD,0.95,100.0,2024-01-01T12:00:00+00:00,,tx-1\n"""
        csv_content += """BROKER_B,CTO,SELL,ASSET-2,,2.0,50.0,0.0,, ,100.0,2024-01-02T12:00:00+00:00,Second transaction,tx-2\n"""

        importer.import_transactions_csv(csv_content)

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
        data_by_ref = {item["external_ref"]: item for item in payload}

        assert data_by_ref["tx-1"]["fee_asset"] == "USD"
        assert data_by_ref["tx-1"]["fx_rate"] == 0.95
        assert data_by_ref["tx-2"]["fee_asset"] is None
        assert data_by_ref["tx-2"]["fx_rate"] == 1.0

        archive = export_zip(db)
        with zipfile.ZipFile(io.BytesIO(archive)) as zf:
            with zf.open("transactions.csv") as transactions_file:
                reader = csv.DictReader(io.TextIOWrapper(transactions_file, encoding="utf-8"))
                rows = {row["external_ref"]: row for row in reader}

        assert rows["tx-1"]["fee_asset"] == "USD"
        assert rows["tx-1"]["fx_rate"] == "0.95"
        assert rows["tx-2"]["fee_asset"] == ""
        assert rows["tx-2"]["fx_rate"] == "1.0"
    finally:
        db.close()
        engine.dispose()


def test_transactions_import_is_idempotent_with_inserted_rows() -> None:
    engine, SessionLocal = _create_session()
    db = SessionLocal()
    try:
        importer = Importer(db)
        header = (
            "source,type_portefeuille,operation,asset,symbol_or_isin,quantity,unit_price_eur," +
            "fee_eur,fee_asset,fx_rate,total_eur,ts,notes,external_ref\n"
        )
        base_rows = [
            "BROKER_A,CTO,BUY,ASSET-1,AAA,1,100,0,,1,100,2024-01-01T12:00:00+00:00,,\n",
            "BROKER_C,PEA,SELL,ASSET-3,CCC,3,40,0.5,,1,119.5,2024-01-03T12:00:00+00:00,,\n",
        ]

        importer.import_transactions_csv(header + "".join(base_rows))
        existing_transactions = {
            (t.source, t.operation, t.asset, t.ts.isoformat()): t.external_ref
            for t in db.query(Transaction).all()
        }

        inserted_row = "BROKER_B,CTO,DIVIDEND,ASSET-2,,2,10,0,,1,20,2024-01-02T12:00:00+00:00,,\n"
        importer.import_transactions_csv(header + base_rows[0] + inserted_row + base_rows[1])

        all_transactions = db.query(Transaction).all()
        assert len(all_transactions) == 3

        for transaction in all_transactions:
            key = (transaction.source, transaction.operation, transaction.asset, transaction.ts.isoformat())
            if key in existing_transactions:
                assert existing_transactions[key] == transaction.external_ref

        expected_inserted_row = dict(
            zip(
                header.strip().split(","),
                inserted_row.strip().split(","),
            )
        )
        expected_ref = compute_external_ref_from_row(expected_inserted_row)
        inserted = next(
            t
            for t in all_transactions
            if (t.source, t.operation, t.asset, t.ts.isoformat())
            not in existing_transactions
        )
        assert inserted.external_ref == expected_ref
    finally:
        db.close()
        engine.dispose()


def test_transactions_import_updates_identical_rows_with_new_external_ref() -> None:
    engine, SessionLocal = _create_session()
    db = SessionLocal()
    try:
        importer = Importer(db)
        header = (
            "source,type_portefeuille,operation,asset,symbol_or_isin,quantity,unit_price_eur," +
            "fee_eur,fee_asset,fx_rate,total_eur,ts,notes,external_ref\n"
        )
        old_external_ref = "legacy_ref_123"
        row_values = [
            "BROKER_A",
            "CTO",
            "BUY",
            "ASSET-1",
            "AAA",
            "1",
            "100",
            "0",
            "",
            "1",
            "100",
            "2024-01-01T12:00:00+00:00",
            "",
            old_external_ref,
        ]
        csv_content = header + ",".join(row_values) + "\n"
        importer.import_transactions_csv(csv_content)

        transaction = db.query(Transaction).one()
        assert transaction.external_ref == old_external_ref

        row_for_computation = dict(
            zip(
                header.strip().split(","),
                row_values,
            )
        )
        row_for_computation["external_ref"] = ""
        expected_external_ref = compute_external_ref_from_row(row_for_computation)

        row_values_with_new_algo = list(row_values)
        row_values_with_new_algo[-1] = ""
        csv_content_reimport = header + ",".join(row_values_with_new_algo) + "\n"
        importer.import_transactions_csv(csv_content_reimport)

        transactions = db.query(Transaction).all()
        assert len(transactions) == 1
        assert transactions[0].external_ref == expected_external_ref
    finally:
        db.close()
        engine.dispose()
