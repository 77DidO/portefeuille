from __future__ import annotations

import zipfile
from datetime import datetime, timezone
from io import BytesIO

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.transactions import Transaction
from app.services.exporter import export_zip
from app.services.importer import Importer


def make_session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/test.db", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, autocommit=False, autoflush=False)


def test_export_import_roundtrip(tmp_path):
    Session = make_session(tmp_path)
    db = Session()
    db.add(
        Transaction(
            source="binance",
            type_portefeuille="CRYPTO",
            operation="BUY",
            asset="Bitcoin",
            symbol_or_isin="BTC",
            quantity=0.05,
            unit_price_eur=25000.0,
            fee_eur=5.0,
            total_eur=1250.0,
            ts=datetime(2024, 3, 1, tzinfo=timezone.utc),
            notes="export test",
            external_ref="ext1",
        )
    )
    db.commit()

    zip_bytes = export_zip(db)
    new_session = Session()
    importer = Importer(new_session)
    importer.import_zip(zip_bytes)

    rows = new_session.query(Transaction).all()
    assert len(rows) == 1
    assert rows[0].external_ref
