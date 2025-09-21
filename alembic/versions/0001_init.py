from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "transactions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("account_id", sa.String(64), nullable=True),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("type_portefeuille", sa.String(16), nullable=False),
        sa.Column("operation", sa.String(16), nullable=False),
        sa.Column("asset", sa.String(64), nullable=False),
        sa.Column("symbol_or_isin", sa.String(64), nullable=True),
        sa.Column("quantity", sa.Float(), nullable=False),
        sa.Column("unit_price_eur", sa.Float(), nullable=False),
        sa.Column("fee_eur", sa.Float(), nullable=False, server_default="0"),
        sa.Column("total_eur", sa.Float(), nullable=False),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("external_ref", sa.String(128), nullable=False),
        sa.UniqueConstraint("external_ref", name="uq_transactions_external_ref"),
    )

    op.create_table(
        "holdings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("account_id", sa.String(64), nullable=True),
        sa.Column("asset", sa.String(64), nullable=False),
        sa.Column("symbol_or_isin", sa.String(64), nullable=True),
        sa.Column("quantity", sa.Float(), nullable=False),
        sa.Column("pru_eur", sa.Float(), nullable=False),
        sa.Column("invested_eur", sa.Float(), nullable=False),
        sa.Column("market_price_eur", sa.Float(), nullable=False),
        sa.Column("market_value_eur", sa.Float(), nullable=False),
        sa.Column("pl_eur", sa.Float(), nullable=False),
        sa.Column("pl_pct", sa.Float(), nullable=False),
        sa.Column("as_of", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "prices",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("asset", sa.String(64), nullable=False),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("price_eur", sa.Float(), nullable=False),
        sa.Column("source", sa.String(32), nullable=False),
        sa.UniqueConstraint("asset", "ts", "source", name="uq_prices_asset_ts_source"),
    )

    op.create_table(
        "snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False, unique=True),
        sa.Column("value_pea_eur", sa.Float(), nullable=False),
        sa.Column("value_crypto_eur", sa.Float(), nullable=False),
        sa.Column("value_total_eur", sa.Float(), nullable=False),
        sa.Column("pnl_total_eur", sa.Float(), nullable=False),
    )

    op.create_table(
        "journal_trades",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("asset", sa.String(64), nullable=False),
        sa.Column("pair", sa.String(32), nullable=False),
        sa.Column("setup", sa.String(64), nullable=True),
        sa.Column("entry", sa.Float(), nullable=True),
        sa.Column("sl", sa.Float(), nullable=True),
        sa.Column("tp", sa.Float(), nullable=True),
        sa.Column("risk_r", sa.Float(), nullable=True),
        sa.Column("result_r", sa.Float(), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="OPEN"),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
    )

    op.create_table(
        "settings",
        sa.Column("key", sa.String(64), primary_key=True),
        sa.Column("value", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "fx_rates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("base", sa.String(8), nullable=False),
        sa.Column("quote", sa.String(8), nullable=False),
        sa.Column("rate", sa.Float(), nullable=False),
        sa.Column("source", sa.String(32), nullable=False),
        sa.UniqueConstraint("ts", "base", "quote", name="uq_fx_rates_ts_base_quote"),
    )

    op.create_table(
        "system_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("level", sa.String(16), nullable=False),
        sa.Column("component", sa.String(64), nullable=False),
        sa.Column("message", sa.String(255), nullable=False),
        sa.Column("meta_json", sa.Text(), nullable=True),
    )

    op.create_table(
        "account_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("account_id", sa.String(64), nullable=False),
        sa.Column("key", sa.String(64), nullable=False),
        sa.Column("value", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("account_settings")
    op.drop_table("system_logs")
    op.drop_table("fx_rates")
    op.drop_table("settings")
    op.drop_table("journal_trades")
    op.drop_table("snapshots")
    op.drop_table("prices")
    op.drop_table("holdings")
    op.drop_table("transactions")
