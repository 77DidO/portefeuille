"""add fee_asset and fx_rate to transactions

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
    op.add_column(
        "transactions",
        sa.Column("fee_asset", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "transactions",
        sa.Column(
            "fx_rate",
            sa.Float(),
            nullable=True,
            server_default=sa.text("1.0"),
        ),
    )

    op.execute("UPDATE transactions SET fx_rate = 1.0 WHERE fx_rate IS NULL")


def downgrade() -> None:
    op.drop_column("transactions", "fx_rate")
    op.drop_column("transactions", "fee_asset")
