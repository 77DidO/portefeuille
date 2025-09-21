from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "holdings",
        sa.Column("type_portefeuille", sa.String(length=16), nullable=True),
    )

    op.execute(
        """
        UPDATE holdings
        SET type_portefeuille = (
            SELECT t.type_portefeuille
            FROM transactions AS t
            WHERE COALESCE(t.account_id, '__NULL__') = COALESCE(holdings.account_id, '__NULL__')
              AND (
                    (t.symbol_or_isin IS NOT NULL AND t.symbol_or_isin != '' AND t.symbol_or_isin = holdings.symbol_or_isin)
                 OR t.asset = holdings.asset
              )
            ORDER BY t.ts DESC, t.id DESC
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
