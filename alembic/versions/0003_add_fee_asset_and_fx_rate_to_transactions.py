"""Update transactions schema with portfolio metadata and harmonised fields.

Revision ID: 0003
Revises: 0002
Create Date: 2024-03-01 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {col["name"] for col in inspector.get_columns("transactions")}

    with op.batch_alter_table("transactions") as batch:
        if "type_portefeuille" in columns and "portfolio_type" not in columns:
            batch.alter_column(
                "type_portefeuille",
                new_column_name="portfolio_type",
                existing_type=sa.String(length=16),
            )
        if "ts" in columns and "trade_date" not in columns:
            batch.alter_column(
                "ts",
                new_column_name="trade_date",
                existing_type=sa.DateTime(timezone=True),
            )
        if "external_ref" in columns and "transaction_uid" not in columns:
            batch.alter_column(
                "external_ref",
                new_column_name="transaction_uid",
                existing_type=sa.String(length=128),
            )
        if "symbol" not in columns:
            batch.add_column(sa.Column("symbol", sa.String(length=64), nullable=True))
        if "isin" not in columns:
            batch.add_column(sa.Column("isin", sa.String(length=32), nullable=True))
        if "mic" not in columns:
            batch.add_column(sa.Column("mic", sa.String(length=16), nullable=True))
        if "fee_asset" not in columns:
            batch.add_column(sa.Column("fee_asset", sa.String(length=64), nullable=True))
        if "fee_quantity" not in columns:
            batch.add_column(sa.Column("fee_quantity", sa.Float(), nullable=True))
        if "fx_rate" in columns:
            batch.drop_column("fx_rate")

    constraints = {c["name"] for c in inspector.get_unique_constraints("transactions")}
    if "uq_transactions_external_ref" in constraints:
        op.drop_constraint("uq_transactions_external_ref", "transactions", type_="unique")
    if "uq_transactions_transaction_uid" not in constraints:
        op.create_unique_constraint(
            "uq_transactions_transaction_uid",
            "transactions",
            ["transaction_uid"],
        )


def downgrade() -> None:
    with op.batch_alter_table("transactions") as batch:
        batch.add_column(sa.Column("fx_rate", sa.Float(), nullable=True))
        batch.drop_column("fee_quantity")
        batch.drop_column("fee_asset")
        batch.drop_column("mic")
        batch.drop_column("isin")
        batch.drop_column("symbol")
        batch.alter_column(
            "transaction_uid",
            new_column_name="external_ref",
            existing_type=sa.String(length=128),
        )
        batch.alter_column(
            "trade_date",
            new_column_name="ts",
            existing_type=sa.DateTime(timezone=True),
        )
        batch.alter_column(
            "portfolio_type",
            new_column_name="type_portefeuille",
            existing_type=sa.String(length=16),
        )

    op.drop_constraint("uq_transactions_transaction_uid", "transactions", type_="unique")
    op.create_unique_constraint(
        "uq_transactions_external_ref",
        "transactions",
        ["external_ref"],
    )
