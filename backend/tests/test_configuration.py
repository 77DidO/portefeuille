from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.configuration import wipe_data
from app.models.base import Base
from app.models.holdings import Holding
from app.models.journal_trades import JournalTrade
from app.models.snapshots import Snapshot
from app.models.transactions import Transaction
from app.services.portfolio import compute_holdings
from app.workers.snapshots import run_snapshot


def setup_db(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/test.db", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, autocommit=False, autoflush=False)


def test_wipe_data_clears_tables_and_cache(tmp_path):
    compute_holdings.cache_clear()
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
                external_ref="wipe-test",
            )
        )
        db.add(
            JournalTrade(
                asset="BTC",
                pair="BTC/EUR",
                setup="test",
                status="OPEN",
                notes="sample",
            )
        )
        db.commit()

        run_snapshot(db)
        holdings_before, _ = compute_holdings(db)
        assert holdings_before, "holdings should be populated before wipe"

        response = wipe_data(db=db, _={})
        assert response == {"status": "ok"}

        assert db.query(Transaction).count() == 0
        assert db.query(JournalTrade).count() == 0
        assert db.query(Snapshot).count() == 0
        assert db.query(Holding).count() == 0

        holdings_after, totals_after = compute_holdings(db)
        assert holdings_after == []
        assert totals_after == {
            "total_value": 0.0,
            "total_invested": 0.0,
            "realized_pnl": 0.0,
            "latent_pnl": 0.0,
        }
    finally:
        db.close()
