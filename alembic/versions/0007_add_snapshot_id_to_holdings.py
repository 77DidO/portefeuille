"""Add snapshot linkage to holdings.

Revision ID: 0007
Revises: 0006
Create Date: 2025-02-15 00:00:00.000001
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "holdings",
        sa.Column("snapshot_id", sa.Integer(), nullable=True),
    )
    op.create_index(
        op.f("ix_holdings_snapshot_id"),
        "holdings",
        ["snapshot_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_holdings_snapshot_id_snapshots",
        "holdings",
        "snapshots",
        ["snapshot_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.execute("DELETE FROM holdings")
    op.alter_column(
        "holdings",
        "snapshot_id",
        existing_type=sa.Integer(),
        nullable=False,
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_holdings_snapshot_id_snapshots", "holdings", type_="foreignkey"
    )
    op.drop_index(op.f("ix_holdings_snapshot_id"), table_name="holdings")
    op.drop_column("holdings", "snapshot_id")
