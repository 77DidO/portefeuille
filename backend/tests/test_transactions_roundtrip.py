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
from app.services.exporter import export_zip
from app.services.importer import Importer


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
