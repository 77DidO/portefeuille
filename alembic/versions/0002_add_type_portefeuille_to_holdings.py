from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    holding_columns = {col["name"] for col in inspector.get_columns("holdings")}
    transaction_columns = {col["name"] for col in inspector.get_columns("transactions")}

    if "type_portefeuille" not in holding_columns:
        op.add_column(
            "holdings",
            sa.Column("type_portefeuille", sa.String(length=16), nullable=True),
        )
        holding_columns.add("type_portefeuille")

    if "type_portefeuille" not in holding_columns:
        return

    portfolio_column = None
    if "type_portefeuille" in transaction_columns:
        portfolio_column = "type_portefeuille"
    elif "portfolio_type" in transaction_columns:
        portfolio_column = "portfolio_type"

    ordering_column = None
    if "ts" in transaction_columns:
        ordering_column = "ts"
    elif "trade_date" in transaction_columns:
        ordering_column = "trade_date"

    if portfolio_column and ordering_column:
        op.execute(
            f"""
            UPDATE holdings
            SET type_portefeuille = (
                SELECT t.{portfolio_column}
                FROM transactions AS t
                WHERE COALESCE(t.account_id, '__NULL__') = COALESCE(holdings.account_id, '__NULL__')
                  AND (
                        (t.symbol_or_isin IS NOT NULL AND t.symbol_or_isin != '' AND t.symbol_or_isin = holdings.symbol_or_isin)
                     OR t.asset = holdings.asset
                  )
                ORDER BY t.{ordering_column} DESC, t.id DESC
                LIMIT 1
            )
            """
        )

    op.execute("UPDATE holdings SET type_portefeuille = 'PEA' WHERE type_portefeuille IS NULL")

    with op.batch_alter_table("holdings") as batch_op:
        batch_op.alter_column(
            "type_portefeuille",
            existing_type=sa.String(length=16),
            nullable=False,
        )


def downgrade() -> None:
    op.drop_column("holdings", "type_portefeuille")
