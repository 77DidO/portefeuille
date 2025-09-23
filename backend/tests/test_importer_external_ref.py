from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.base import Base
from app.models.transactions import Transaction
from app.services.importer import Importer, REQUIRED_COLUMNS


CSV_HEADER = ",".join(REQUIRED_COLUMNS["transactions.csv"]) + "\n"


def _create_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine)
    return engine, TestingSessionLocal


def test_importer_uses_external_id_and_persists_mic_and_fees() -> None:
    engine, SessionLocal = _create_session()
    db = SessionLocal()
    try:
        importer = Importer(db)
        csv_content = (
            CSV_HEADER
            + "external-123,DEGIRO,CTO,BUY,2024-01-05T10:00:00+00:00,ASSET-EXT,ASX,US0987654321,XNAS,5,20,100,1.2,USD,1.3,Imported with MIC\n"
        )

        importer.import_transactions_csv(csv_content)

        transaction = db.query(Transaction).one()
        assert transaction.transaction_uid == "external-123"
        assert transaction.mic == "XNAS"
        assert transaction.fee_asset == "USD"
        assert transaction.fee_quantity == 1.3
    finally:
        db.close()
        engine.dispose()
