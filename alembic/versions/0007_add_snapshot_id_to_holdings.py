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
    with op.batch_alter_table("holdings") as batch:
        batch.add_column(sa.Column("snapshot_id", sa.Integer(), nullable=True))
        batch.create_index(
            batch.f("ix_holdings_snapshot_id"),
            ["snapshot_id"],
            unique=False,
        )
        batch.create_foreign_key(
            batch.f("fk_holdings_snapshot_id_snapshots"),
            "snapshots",
            ["snapshot_id"],
            ["id"],
            ondelete="CASCADE",
        )

    op.execute("DELETE FROM holdings")

    with op.batch_alter_table("holdings") as batch:
        batch.alter_column(
            "snapshot_id",
            existing_type=sa.Integer(),
            nullable=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("holdings") as batch:
        batch.drop_constraint(
            batch.f("fk_holdings_snapshot_id_snapshots"), type_="foreignkey"
        )
        batch.drop_index(batch.f("ix_holdings_snapshot_id"))
        batch.drop_column("snapshot_id")
