from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.snapshots import Snapshot
from app.models.transactions import Transaction
from app.workers.snapshots import run_snapshot


def setup_db(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/test.db", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, autocommit=False, autoflush=False)


def test_snapshot_inserts_once_per_call(tmp_path):
    Session = setup_db(tmp_path)
    db = Session()
    try:
        db.add(
            Transaction(
                source="binance",
                type_portefeuille="CRYPTO",
                operation="BUY",
                asset="Bitcoin",
                symbol_or_isin="BTC",
                quantity=0.1,
                unit_price_eur=20000.0,
                fee_eur=10.0,
                total_eur=2000.0,
                ts=datetime(2024, 1, 1, tzinfo=timezone.utc),
                notes="",
                external_ref="test",
            )
        )
        db.commit()
        run_snapshot(db)
        run_snapshot(db)
        count = db.query(Snapshot).count()
        assert count == 2
    finally:
        db.close()
