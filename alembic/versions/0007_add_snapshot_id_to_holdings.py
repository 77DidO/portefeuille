"""Add snapshot linkage to holdings.

Revision ID: 0007
Revises: 0006
Create Date: 2024-03-20 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("holdings", recreate="auto") as batch_op:
        batch_op.add_column(sa.Column("snapshot_id", sa.Integer(), nullable=True))
        batch_op.create_index(
            batch_op.f("ix_holdings_snapshot_id"),
            ["snapshot_id"],
            unique=False,
        )
        batch_op.create_foreign_key(
            "fk_holdings_snapshot_id_snapshots",
            "snapshots",
            ["snapshot_id"],
            ["id"],
            ondelete="CASCADE",
        )

    op.execute("DELETE FROM holdings")

    with op.batch_alter_table("holdings", recreate="auto") as batch_op:
        batch_op.alter_column(
            "snapshot_id",
            existing_type=sa.Integer(),
            nullable=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("holdings", recreate="auto") as batch_op:
        batch_op.alter_column(
            "snapshot_id",
            existing_type=sa.Integer(),
            nullable=True,
        )
        batch_op.drop_constraint(
            "fk_holdings_snapshot_id_snapshots",
            type_="foreignkey",
        )
        batch_op.drop_index(batch_op.f("ix_holdings_snapshot_id"))
        batch_op.drop_column("snapshot_id")
