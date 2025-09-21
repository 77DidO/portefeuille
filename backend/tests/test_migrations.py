from __future__ import annotations

from sqlalchemy import create_engine, inspect

from app.core.config import settings
from app.db.migration import run_migrations


LEGACY_TABLE_DEFINITIONS = {
    "transactions": """
        CREATE TABLE transactions (
            id INTEGER PRIMARY KEY,
            account_id VARCHAR(64),
            source VARCHAR(32) NOT NULL,
            type_portefeuille VARCHAR(16) NOT NULL,
            operation VARCHAR(16) NOT NULL,
            asset VARCHAR(64) NOT NULL,
            symbol_or_isin VARCHAR(64),
            quantity FLOAT NOT NULL,
            unit_price_eur FLOAT NOT NULL,
            fee_eur FLOAT NOT NULL DEFAULT 0,
            total_eur FLOAT NOT NULL,
            ts DATETIME NOT NULL,
            notes TEXT,
            external_ref VARCHAR(128) NOT NULL,
            CONSTRAINT uq_transactions_external_ref UNIQUE (external_ref)
        )
    """,
    "holdings": """
        CREATE TABLE holdings (
            id INTEGER PRIMARY KEY,
            account_id VARCHAR(64),
            asset VARCHAR(64) NOT NULL,
            symbol_or_isin VARCHAR(64),
            quantity FLOAT NOT NULL,
            pru_eur FLOAT NOT NULL,
            invested_eur FLOAT NOT NULL,
            market_price_eur FLOAT NOT NULL,
            market_value_eur FLOAT NOT NULL,
            pl_eur FLOAT NOT NULL,
            pl_pct FLOAT NOT NULL,
            as_of DATETIME NOT NULL
        )
    """,
    "prices": """
        CREATE TABLE prices (
            id INTEGER PRIMARY KEY,
            asset VARCHAR(64) NOT NULL,
            ts DATETIME NOT NULL,
            price_eur FLOAT NOT NULL,
            source VARCHAR(32) NOT NULL,
            CONSTRAINT uq_prices_asset_ts_source UNIQUE (asset, ts, source)
        )
    """,
    "snapshots": """
        CREATE TABLE snapshots (
            id INTEGER PRIMARY KEY,
            ts DATETIME NOT NULL UNIQUE,
            value_pea_eur FLOAT NOT NULL,
            value_crypto_eur FLOAT NOT NULL,
            value_total_eur FLOAT NOT NULL,
            pnl_total_eur FLOAT NOT NULL
        )
    """,
    "journal_trades": """
        CREATE TABLE journal_trades (
            id INTEGER PRIMARY KEY,
            asset VARCHAR(64) NOT NULL,
            pair VARCHAR(32) NOT NULL,
            setup VARCHAR(64),
            entry FLOAT,
            sl FLOAT,
            tp FLOAT,
            risk_r FLOAT,
            result_r FLOAT,
            status VARCHAR(16) NOT NULL DEFAULT 'OPEN',
            opened_at DATETIME,
            closed_at DATETIME,
            notes TEXT
        )
    """,
    "settings": """
        CREATE TABLE settings (
            key VARCHAR(64) PRIMARY KEY,
            value TEXT,
            updated_at DATETIME NOT NULL
        )
    """,
    "fx_rates": """
        CREATE TABLE fx_rates (
            id INTEGER PRIMARY KEY,
            ts DATETIME NOT NULL,
            base VARCHAR(8) NOT NULL,
            quote VARCHAR(8) NOT NULL,
            rate FLOAT NOT NULL,
            source VARCHAR(32) NOT NULL,
            CONSTRAINT uq_fx_rates_ts_base_quote UNIQUE (ts, base, quote)
        )
    """,
    "system_logs": """
        CREATE TABLE system_logs (
            id INTEGER PRIMARY KEY,
            ts DATETIME NOT NULL,
            level VARCHAR(16) NOT NULL,
            component VARCHAR(64) NOT NULL,
            message VARCHAR(255) NOT NULL,
            meta_json TEXT
        )
    """,
    "account_settings": """
        CREATE TABLE account_settings (
            id INTEGER PRIMARY KEY,
            account_id VARCHAR(64) NOT NULL,
            key VARCHAR(64) NOT NULL,
            value TEXT,
            updated_at DATETIME NOT NULL
        )
    """,
}


def test_run_migrations_from_legacy_schema(tmp_path, monkeypatch):
    db_path = tmp_path / "legacy.db"
    database_url = f"sqlite:///{db_path}"

    engine = create_engine(database_url)

    try:
        with engine.begin() as connection:
            for ddl in LEGACY_TABLE_DEFINITIONS.values():
                connection.exec_driver_sql(ddl)

        monkeypatch.setattr(settings, "database_url", database_url)

        run_migrations()

        with create_engine(database_url).connect() as connection:
            inspector = inspect(connection)
            assert inspector.has_table("alembic_version")
            holdings_columns = {col["name"] for col in inspector.get_columns("holdings")}
            assert "type_portefeuille" in holdings_columns
    finally:
        engine.dispose()
