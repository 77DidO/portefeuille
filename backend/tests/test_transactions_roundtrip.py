from __future__ import annotations

import csv
import io
import zipfile
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import deps
from app.api import export as export_api
from app.api import transactions as transactions_api
from app.models.base import Base
from app.models.transactions import Transaction
from app.services.exporter import export_zip
from app.services.importer import (
    Importer,
    REQUIRED_COLUMNS,
    compute_transaction_uid_from_row,
)


CSV_COLUMNS = list(REQUIRED_COLUMNS["transactions.csv"])
CSV_HEADER = ",".join(CSV_COLUMNS) + "\n"


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
        rows = [
            [
                "tx-1",
                "BROKER_A",
                "CTO",
                "BUY",
                "2024-01-01T12:00:00+00:00",
                "ASSET-1",
                "AAA",
                "",
                "",
                "1.0",
                "100.0",
                "100.0",
                "1.0",
                "USD",
                "",
                "",
            ],
            [
                "tx-2",
                "BROKER_B",
                "CTO",
                "SELL",
                "2024-01-02T12:00:00+00:00",
                "ASSET-2",
                "",
                "US1234567890",
                "XPAR",
                "2.0",
                "50.0",
                "100.0",
                "",
                "BTC",
                "0.0001",
                "Second transaction",
            ],
        ]
        csv_content = CSV_HEADER + "".join(",".join(row) + "\n" for row in rows)

        importer.import_transactions_csv(csv_content)

        transactions = {t.transaction_uid: t for t in db.query(Transaction).all()}
        assert transactions["tx-1"].fee_asset == "USD"
        assert transactions["tx-1"].fee_quantity is None
        assert transactions["tx-2"].fee_asset == "BTC"
        assert transactions["tx-2"].fee_quantity == 0.0001
        assert transactions["tx-2"].fee_eur == 0
        assert transactions["tx-2"].mic == "XPAR"

        archive = export_zip(db)
        with zipfile.ZipFile(io.BytesIO(archive)) as zf:
            with zf.open("transactions.csv") as transactions_file:
                reader = csv.DictReader(io.TextIOWrapper(transactions_file, encoding="utf-8"))
                assert reader.fieldnames == CSV_COLUMNS
                exported_rows = {row["id"]: row for row in reader}

        assert exported_rows["tx-1"]["fee_asset"] == "USD"
        assert exported_rows["tx-1"]["fee_quantity"] == ""
        assert exported_rows["tx-2"]["fee_asset"] == "BTC"
        assert exported_rows["tx-2"]["fee_quantity"] == "0.0001"
        assert exported_rows["tx-2"]["fee_eur"] == "0"
        assert exported_rows["tx-2"]["isin"] == "US1234567890"
        assert exported_rows["tx-2"]["mic"] == "XPAR"

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
        data_by_ref = {item["csv_transaction_id"]: item for item in payload}

        assert data_by_ref["tx-1"]["fee_asset"] == "USD"
        assert data_by_ref["tx-2"]["fee_asset"] == "BTC"
        assert data_by_ref["tx-2"]["fee_eur"] == 0
        assert data_by_ref["tx-2"]["mic"] == "XPAR"
    finally:
        db.close()
        engine.dispose()


def test_export_zip_route_exposes_new_transactions_columns() -> None:
    engine, SessionLocal = _create_session()
    db = SessionLocal()
    try:
        db.add(
            Transaction(
                source="BROKER_C",
                portfolio_type="CTO",
                operation="BUY",
                asset="ASSET-3",
                symbol_or_isin="ASSET-3",
                symbol="AS3",
                isin="FR0000000001",
                mic="XPAR",
                quantity=3.0,
                unit_price_eur=25.0,
                fee_eur=0.75,
                fee_asset="EUR",
                fee_quantity=None,
                total_eur=75.0,
                trade_date=datetime(2024, 1, 3, 12, 0, tzinfo=timezone.utc),
                notes="Export via API",
                transaction_uid="tx-api",
            )
        )
        db.commit()

        def override_get_db():
            session = SessionLocal()
            try:
                yield session
            finally:
                session.close()

        app = FastAPI()
        app.include_router(export_api.router)
        app.dependency_overrides[deps.get_db] = override_get_db

        client = TestClient(app)
        response = client.get("/export/zip")
        assert response.status_code == 200

        with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
            with zf.open("transactions.csv") as transactions_file:
                reader = csv.DictReader(io.TextIOWrapper(transactions_file, encoding="utf-8"))
                assert reader.fieldnames == CSV_COLUMNS
                rows = list(reader)

        assert len(rows) == 1
        exported = rows[0]
        assert exported["id"] == "tx-api"
        assert exported["mic"] == "XPAR"
        assert exported["fee_asset"] == "EUR"
        assert exported["fee_quantity"] == ""
    finally:
        db.close()
        engine.dispose()



def test_transactions_import_is_idempotent_with_inserted_rows() -> None:
    engine, SessionLocal = _create_session()
    db = SessionLocal()
    try:
        importer = Importer(db)
        base_rows = [
            ",BROKER_A,CTO,BUY,2024-01-01T12:00:00+00:00,ASSET-1,AAA,,,1,100,100,0,,,\n",
            ",BROKER_C,PEA,SELL,2024-01-03T12:00:00+00:00,ASSET-3,CCC,,,3,40,119.5,0.5,,,\n",
        ]

        importer.import_transactions_csv(CSV_HEADER + "".join(base_rows))
        existing_transactions = {
            (t.source, t.operation, t.asset, t.trade_date.isoformat()): t.transaction_uid
            for t in db.query(Transaction).all()
        }

        inserted_row = ",BROKER_B,CTO,DIVIDEND,2024-01-02T12:00:00+00:00,ASSET-2,,,,2,10,20,,,\n"
        importer.import_transactions_csv(CSV_HEADER + base_rows[0] + inserted_row + base_rows[1])

        all_transactions = db.query(Transaction).all()
        assert len(all_transactions) == 3

        for transaction in all_transactions:
            key = (transaction.source, transaction.operation, transaction.asset, transaction.trade_date.isoformat())
            if key in existing_transactions:
                assert existing_transactions[key] == transaction.transaction_uid

        expected_inserted_row = dict(
            zip(
                CSV_COLUMNS,
                inserted_row.strip().split(","),
            )
        )
        expected_ref = compute_transaction_uid_from_row(expected_inserted_row)
        inserted = next(
            t
            for t in all_transactions
            if (t.source, t.operation, t.asset, t.trade_date.isoformat())
            not in existing_transactions
        )
        assert inserted.transaction_uid == expected_ref
    finally:
        db.close()
        engine.dispose()


def test_transactions_import_updates_identical_rows_with_new_transaction_uid() -> None:
    engine, SessionLocal = _create_session()
    db = SessionLocal()
    try:
        importer = Importer(db)
        row_values = [
            "legacy_ref_123",
            "BROKER_A",
            "CTO",
            "BUY",
            "2024-01-01T12:00:00+00:00",
            "ASSET-1",
            "AAA",
            "",
            "",
            "1",
            "100",
            "100",
            "0",
            "",
            "",
            "",
        ]
        csv_content = CSV_HEADER + ",".join(row_values) + "\n"
        importer.import_transactions_csv(csv_content)

        transaction = db.query(Transaction).one()
        assert transaction.transaction_uid == "legacy_ref_123"

        row_for_computation = dict(zip(CSV_COLUMNS, row_values))
        row_for_computation["id"] = ""
        expected_transaction_uid = compute_transaction_uid_from_row(row_for_computation)

        row_values_with_new_algo = list(row_values)
        row_values_with_new_algo[0] = ""
        csv_content_reimport = CSV_HEADER + ",".join(row_values_with_new_algo) + "\n"
        importer.import_transactions_csv(csv_content_reimport)

        transactions = db.query(Transaction).all()
        assert len(transactions) == 1
        assert transactions[0].transaction_uid == expected_transaction_uid
    finally:
        db.close()
        engine.dispose()


def test_transactions_import_handles_none_string_notes() -> None:
    engine, SessionLocal = _create_session()
    db = SessionLocal()
    try:
        importer = Importer(db)
        original_trade_date = "2024-01-01T12:00:00+00:00"
        original_row = (
            f"legacy_ref,BROKER_A,CTO,BUY,{original_trade_date},ASSET-1,AAA,,,1,100,100,0,,,None\n"
        )

        importer.import_transactions_csv(CSV_HEADER + original_row)

        transaction = db.query(Transaction).one()
        assert transaction.notes is None

        archive = export_zip(db)
        with zipfile.ZipFile(io.BytesIO(archive)) as zf:
            with zf.open("transactions.csv") as transactions_file:
                reader = csv.DictReader(io.TextIOWrapper(transactions_file, encoding="utf-8"))
                exported_rows = list(reader)

        assert len(exported_rows) == 1
        exported_row = exported_rows[0]
        exported_row["notes"] = exported_row["notes"] or "None"
        exported_row["id"] = ""

        reimport_content = io.StringIO()
        writer = csv.writer(reimport_content)
        writer.writerow(CSV_COLUMNS)
        writer.writerow([exported_row[column] for column in CSV_COLUMNS])

        reimport_buffer = io.BytesIO()
        with zipfile.ZipFile(reimport_buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("transactions.csv", reimport_content.getvalue())

        reimport_buffer.seek(0)
        importer.import_zip(reimport_buffer.read())

        transactions = db.query(Transaction).all()
        assert len(transactions) == 1

        expected_row_for_ref = {column: exported_row[column] for column in CSV_COLUMNS}
        expected_transaction_uid = compute_transaction_uid_from_row(expected_row_for_ref)

        refreshed_transaction = transactions[0]
        assert refreshed_transaction.transaction_uid == expected_transaction_uid
        assert refreshed_transaction.notes is None
    finally:
        db.close()
        engine.dispose()
