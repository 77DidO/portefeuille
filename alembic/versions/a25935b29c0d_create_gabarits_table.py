"""create gabarits table

Revision ID: a25935b29c0d
Revises: 0007
Create Date: 2025-09-26 16:26:58.089621
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "a25935b29c0d"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "gabarits",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("nom", sa.String(length=255), nullable=False, unique=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("contenu", sa.Text(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("gabarits")
