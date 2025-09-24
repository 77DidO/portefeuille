from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text


revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    holdings_columns = {column["name"] for column in inspector.get_columns("holdings")}
    transaction_columns = {column["name"] for column in inspector.get_columns("transactions")}

    if "type_portefeuille" not in holdings_columns:
        op.add_column(
            "holdings",
            sa.Column("type_portefeuille", sa.String(length=16), nullable=True),
        )
        holdings_columns.add("type_portefeuille")

    source_column = None
    for candidate in ("type_portefeuille", "portfolio_type"):
        if candidate in transaction_columns:
            source_column = candidate
            break

    order_column = "id"
    for candidate in ("ts", "trade_date"):
        if candidate in transaction_columns:
            order_column = candidate
            break

    if source_column is not None and "type_portefeuille" in holdings_columns:
        op.execute(
            text(
                f"""
                UPDATE holdings
                SET type_portefeuille = (
                    SELECT t.{source_column}
                    FROM transactions AS t
                    WHERE COALESCE(t.account_id, '__NULL__') = COALESCE(holdings.account_id, '__NULL__')
                      AND (
                            (t.symbol_or_isin IS NOT NULL AND t.symbol_or_isin != '' AND t.symbol_or_isin = holdings.symbol_or_isin)
                         OR t.asset = holdings.asset
                      )
                    ORDER BY t.{order_column} DESC, t.id DESC
                    LIMIT 1
                )
                """
            )
        )

    if "type_portefeuille" in holdings_columns:
        op.execute(
            "UPDATE holdings SET type_portefeuille = 'PEA' WHERE type_portefeuille IS NULL"
        )

        with op.batch_alter_table("holdings") as batch_op:
            batch_op.alter_column(
                "type_portefeuille",
                existing_type=sa.String(length=16),
                nullable=False,
            )


def downgrade() -> None:
    op.drop_column("holdings", "type_portefeuille")
