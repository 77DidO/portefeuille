from __future__ import annotations

import io
import zipfile
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.transactions import Transaction
from app.services.importer import ImportErrorDetail, Importer


@pytest.fixture
def db_session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/test.db", connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


def make_zip(content: str) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr("transactions.csv", content)
    buffer.seek(0)
    return buffer.read()


def test_import_success(db_session):
    csv_content = """source,type_portefeuille,operation,asset,symbol_or_isin,quantity,unit_price_eur,fee_eur,total_eur,ts\n"
    csv_content += "binance,CRYPTO,BUY,Bitcoin,BTC,0.1,30000,10,3000,2024-01-01T00:00:00Z\n"
    importer = Importer(db_session)
    importer.import_zip(make_zip(csv_content))
    assert db_session.query(Transaction).count() == 1


def test_import_missing_column(db_session):
    csv_content = """source,type_portefeuille,asset,symbol_or_isin,quantity,unit_price_eur,fee_eur,total_eur,ts\n"""
    importer = Importer(db_session)
    with pytest.raises(ImportErrorDetail):
        importer.import_zip(make_zip(csv_content))
