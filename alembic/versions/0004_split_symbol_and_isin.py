"""split symbol and isin

Revision ID: 0004
Revises: 0003
Create Date: 2025-09-23 11:32:45.345543
"""

from __future__ import annotations

from typing import Iterable

from alembic import op
import sqlalchemy as sa


revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def _transactions_table(column_names: Iterable[str]) -> sa.Table:
    columns = [sa.column("id", sa.Integer)]
    if "symbol_or_isin" in column_names:
        columns.append(sa.column("symbol_or_isin", sa.String(length=64)))
    if "symbol" in column_names:
        columns.append(sa.column("symbol", sa.String(length=64)))
    if "isin" in column_names:
        columns.append(sa.column("isin", sa.String(length=32)))
    if "mic" in column_names:
        columns.append(sa.column("mic", sa.String(length=16)))
    if "fee_quantity" in column_names:
        columns.append(sa.column("fee_quantity", sa.Float()))
    if "transaction_uid" in column_names:
        columns.append(sa.column("transaction_uid", sa.String(length=128)))
    if "external_ref" in column_names:
        columns.append(sa.column("external_ref", sa.String(length=128)))
    if "portfolio_type" in column_names:
        columns.append(sa.column("portfolio_type", sa.String(length=16)))
    if "type_portefeuille" in column_names:
        columns.append(sa.column("type_portefeuille", sa.String(length=16)))
    if "trade_date" in column_names:
        columns.append(sa.column("trade_date", sa.DateTime(timezone=True)))
    if "ts" in column_names:
        columns.append(sa.column("ts", sa.DateTime(timezone=True)))
    if "created_at" in column_names:
        columns.append(sa.column("created_at", sa.DateTime(timezone=True)))
    return sa.table("transactions", *columns)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    column_info = {col["name"]: col for col in inspector.get_columns("transactions")}

    had_portfolio_type = "portfolio_type" in column_info
    had_transaction_uid = "transaction_uid" in column_info

    with op.batch_alter_table("transactions") as batch:
        if "type_portefeuille" in column_info and "portfolio_type" not in column_info:
            batch.alter_column(
                "type_portefeuille",
                new_column_name="portfolio_type",
                existing_type=column_info["type_portefeuille"]["type"],
                existing_nullable=column_info["type_portefeuille"]["nullable"],
            )
        if "portfolio_type" not in column_info:
            batch.add_column(sa.Column("portfolio_type", sa.String(length=16), nullable=True))

        if "external_ref" in column_info and "transaction_uid" not in column_info:
            batch.alter_column(
                "external_ref",
                new_column_name="transaction_uid",
                existing_type=column_info["external_ref"]["type"],
                existing_nullable=column_info["external_ref"]["nullable"],
            )
        if "transaction_uid" not in column_info:
            batch.add_column(sa.Column("transaction_uid", sa.String(length=128), nullable=True))

        if "ts" in column_info and "trade_date" not in column_info:
            batch.alter_column(
                "ts",
                new_column_name="trade_date",
                existing_type=column_info["ts"]["type"],
                existing_nullable=column_info["ts"]["nullable"],
            )
        if "trade_date" not in column_info:
            batch.add_column(sa.Column("trade_date", sa.DateTime(timezone=True), nullable=True))

        if "symbol" not in column_info:
            batch.add_column(sa.Column("symbol", sa.String(length=64), nullable=True))
        if "isin" not in column_info:
            batch.add_column(sa.Column("isin", sa.String(length=32), nullable=True))
        if "mic" not in column_info:
            batch.add_column(sa.Column("mic", sa.String(length=16), nullable=True))
        if "fee_quantity" not in column_info:
            batch.add_column(sa.Column("fee_quantity", sa.Float(), nullable=True))

    inspector = sa.inspect(bind)
    column_info = {col["name"]: col for col in inspector.get_columns("transactions")}
    column_names = set(column_info)
    transactions = _transactions_table(column_names)

    unique_constraints = {c["name"] for c in inspector.get_unique_constraints("transactions")}
    if "uq_transactions_external_ref" in unique_constraints:
        op.drop_constraint("uq_transactions_external_ref", "transactions", type_="unique")
    if "transaction_uid" in column_names and "uq_transactions_transaction_uid" not in unique_constraints:
        op.create_unique_constraint(
            "uq_transactions_transaction_uid",
            "transactions",
            ["transaction_uid"],
        )

    if "transaction_uid" in column_names and "external_ref" in column_names:
        bind.execute(
            sa.text(
                """
                UPDATE transactions
                SET transaction_uid = external_ref
                WHERE transaction_uid IS NULL AND external_ref IS NOT NULL
                """
            )
        )

    if "trade_date" in column_names:
        if "created_at" in column_names:
            bind.execute(
                sa.text(
                    """
                    UPDATE transactions
                    SET trade_date = created_at
                    WHERE trade_date IS NULL AND created_at IS NOT NULL
                    """
                )
            )
        if "ts" in column_names:
            bind.execute(
                sa.text(
                    """
                    UPDATE transactions
                    SET trade_date = ts
                    WHERE trade_date IS NULL AND ts IS NOT NULL
                    """
                )
            )
        bind.execute(
            sa.text(
                """
                UPDATE transactions
                SET trade_date = CURRENT_TIMESTAMP
                WHERE trade_date IS NULL
                """
            )
        )

    if {"symbol_or_isin", "symbol", "isin"}.issubset(column_names):
        rows = bind.execute(
            sa.select(
                transactions.c.id,
                transactions.c.symbol_or_isin,
                transactions.c.symbol,
                transactions.c.isin,
            )
        ).all()

        for row in rows:
            raw_value = (row.symbol_or_isin or "").strip()
            if not raw_value:
                continue
            if (row.symbol and row.symbol.strip()) or (row.isin and row.isin.strip()):
                continue

            normalized = raw_value.replace(" ", "").upper()
            is_isin = (
                len(normalized) == 12
                and normalized[:2].isalpha()
                and normalized.isalnum()
            )
            symbol_value = None if is_isin else raw_value
            isin_value = normalized if is_isin else None

            bind.execute(
                sa.update(transactions)
                .where(transactions.c.id == row.id)
                .values(symbol=symbol_value, isin=isin_value)
            )

    if "transaction_uid" in column_names:
        rows = bind.execute(
            sa.select(transactions.c.id, transactions.c.transaction_uid)
        ).all()
        for row in rows:
            current_uid = (row.transaction_uid or "").strip()
            if current_uid:
                continue
            fallback_uid = f"legacy-tx-{row.id}"
            bind.execute(
                sa.update(transactions)
                .where(transactions.c.id == row.id)
                .values(transaction_uid=fallback_uid)
            )

    needs_not_null_updates = any(
        [
            "trade_date" in column_names,
            "transaction_uid" in column_names and not had_transaction_uid,
            "portfolio_type" in column_names and had_portfolio_type,
        ]
    )

    if needs_not_null_updates:
        with op.batch_alter_table("transactions") as batch:
            if "transaction_uid" in column_names and not had_transaction_uid:
                batch.alter_column(
                    "transaction_uid",
                    existing_type=column_info["transaction_uid"]["type"],
                    nullable=False,
                )
            if "trade_date" in column_names:
                batch.alter_column(
                    "trade_date",
                    existing_type=column_info["trade_date"]["type"],
                    nullable=False,
                )
            if "portfolio_type" in column_names and had_portfolio_type:
                batch.alter_column(
                    "portfolio_type",
                    existing_type=column_info["portfolio_type"]["type"],
                    nullable=False,
                )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    column_info = {col["name"]: col for col in inspector.get_columns("transactions")}
    column_names = set(column_info)
    transactions = _transactions_table(column_names)

    if {"symbol_or_isin", "symbol", "isin"}.issubset(column_names):
        bind.execute(
            sa.text(
                """
                UPDATE transactions
                SET symbol_or_isin = CASE
                    WHEN isin IS NOT NULL AND TRIM(isin) != '' THEN isin
                    WHEN symbol IS NOT NULL AND TRIM(symbol) != '' THEN symbol
                    ELSE symbol_or_isin
                END
                """
            )
        )
        bind.execute(sa.text("UPDATE transactions SET symbol = NULL"))
        bind.execute(sa.text("UPDATE transactions SET isin = NULL"))

    if "external_ref" in column_names and "transaction_uid" in column_names:
        bind.execute(
            sa.text(
                """
                UPDATE transactions
                SET external_ref = transaction_uid
                WHERE transaction_uid IS NOT NULL
                """
            )
        )

    if "created_at" in column_names and "trade_date" in column_names:
        bind.execute(
            sa.text(
                """
                UPDATE transactions
                SET created_at = trade_date
                WHERE created_at IS NULL AND trade_date IS NOT NULL
                """
            )
        )
