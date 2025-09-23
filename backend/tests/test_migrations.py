from __future__ import annotations

import os
from datetime import datetime
from typing import Iterable, Tuple
from uuid import uuid4
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError

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
            ts DATETIME,
            created_at DATETIME,
            notes TEXT,
            external_ref VARCHAR(128),
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


def _build_database_matrix(tmp_path) -> Iterable[Tuple[str, str, Tuple[str, str] | None]]:
    sqlite_url = f"sqlite:///{tmp_path / 'legacy.db'}"
    yield ("sqlite", sqlite_url, None)

    postgres_url = os.getenv("TEST_POSTGRES_URL")
    if not postgres_url:
        return

    url = make_url(postgres_url)
    admin_database = url.database or "postgres"
    db_name = f"{(url.database or 'portefeuille')}_legacy_{uuid4().hex[:8]}"
    admin_url = url.set(database=admin_database)

    try:
        admin_engine = create_engine(admin_url)
        with admin_engine.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
            connection.exec_driver_sql(f'DROP DATABASE IF EXISTS "{db_name}"')
            connection.exec_driver_sql(f'CREATE DATABASE "{db_name}"')
    except OperationalError:  # pragma: no cover - exercised only with misconfigured env
        return
    finally:
        admin_engine.dispose()

    yield (
        "postgresql",
        str(url.set(database=db_name)),
        (str(admin_url), db_name),
    )


def test_run_migrations_from_legacy_schema(tmp_path, monkeypatch):
    cleanup_tasks: list[Tuple[str, str]] = []

    try:
        for dialect, database_url, cleanup in _build_database_matrix(tmp_path):
            connect_args = {"check_same_thread": False} if dialect == "sqlite" else {}
            engine = create_engine(database_url, connect_args=connect_args)

            try:
                with engine.begin() as connection:
                    for ddl in LEGACY_TABLE_DEFINITIONS.values():
                        connection.exec_driver_sql(ddl)

                    connection.execute(
                        text(
                            """
                            INSERT INTO transactions (
                                account_id,
                                source,
                                type_portefeuille,
                                operation,
                                asset,
                                symbol_or_isin,
                                quantity,
                                unit_price_eur,
                                fee_eur,
                                total_eur,
                                ts,
                                created_at,
                                notes,
                                external_ref
                            )
                            VALUES
                                (
                                    'ACC-1',
                                    'BROKER_A',
                                    'PEA',
                                    'BUY',
                                    'ASSET-1',
                                    ' btc ',
                                    1.0,
                                    100.0,
                                    1.0,
                                    100.0,
                                    :ts1,
                                    NULL,
                                    NULL,
                                    'legacy-external-1'
                                ),
                                (
                                    'ACC-2',
                                    'BROKER_B',
                                    'CTO',
                                    'SELL',
                                    'ASSET-2',
                                    'fr0000120271',
                                    2.0,
                                    50.0,
                                    0.5,
                                    100.0,
                                    NULL,
                                    :created_at2,
                                    'legacy row',
                                    NULL
                                )
                            """
                        ),
                        {
                            "ts1": datetime(2024, 1, 1, 12, 0, 0),
                            "created_at2": datetime(2024, 1, 2, 9, 30, 0),
                        },
                    )

                monkeypatch.setattr(settings, "database_url", database_url)

                run_migrations()

                with create_engine(database_url, connect_args=connect_args).connect() as connection:
                    inspector = inspect(connection)
                    assert inspector.has_table("alembic_version")
                    transactions_columns = {col["name"] for col in inspector.get_columns("transactions")}
                    expected_columns = {
                        "portfolio_type",
                        "trade_date",
                        "symbol",
                        "isin",
                        "mic",
                        "fee_asset",
                        "fee_quantity",
                        "transaction_uid",
                    }
                    assert expected_columns.issubset(transactions_columns)

                    constraints = {c["name"] for c in inspector.get_unique_constraints("transactions")}
                    assert "uq_transactions_transaction_uid" in constraints

                    rows = connection.execute(
                        text(
                            "SELECT id, symbol_or_isin, symbol, isin, transaction_uid, trade_date, portfolio_type "
                            "FROM transactions ORDER BY id"
                        )
                    ).mappings().all()

                    assert rows[0]["symbol_or_isin"].strip() == "btc"
                    assert rows[0]["symbol"] == "btc"
                    assert rows[0]["isin"] is None
                    assert rows[0]["transaction_uid"] == "legacy-external-1"
                    assert rows[0]["trade_date"] is not None
                    assert rows[0]["portfolio_type"] == "PEA"

                    assert rows[1]["symbol_or_isin"].strip() == "fr0000120271"
                    assert rows[1]["symbol"] is None
                    assert rows[1]["isin"] == "FR0000120271"
                    assert rows[1]["transaction_uid"].startswith("legacy-tx-")
                    assert rows[1]["trade_date"] is not None
                    assert rows[1]["portfolio_type"] == "CTO"

                    holdings_columns = {col["name"] for col in inspector.get_columns("holdings")}
                    assert {"portfolio_type", "symbol", "isin", "mic"}.issubset(holdings_columns)
                    assert "type_portefeuille" not in holdings_columns
            finally:
                engine.dispose()
                if cleanup:
                    cleanup_tasks.append(cleanup)
    finally:
        for admin_url, db_name in cleanup_tasks:
            admin_engine = create_engine(admin_url)
            try:
                with admin_engine.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
                    connection.exec_driver_sql(f'DROP DATABASE IF EXISTS "{db_name}"')
            finally:
                admin_engine.dispose()
