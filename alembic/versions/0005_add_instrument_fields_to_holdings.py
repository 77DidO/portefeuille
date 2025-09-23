"""add instrument fields to holdings

Revision ID: 0005
Revises: 0004
Create Date: 2025-09-24 00:00:00.000000
"""

from __future__ import annotations

from typing import Iterable

from alembic import op
import sqlalchemy as sa


revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def _holdings_table(column_names: Iterable[str]) -> sa.Table:
    columns = [sa.column("id", sa.Integer)]
    if "symbol_or_isin" in column_names:
        columns.append(sa.column("symbol_or_isin", sa.String(length=64)))
    if "symbol" in column_names:
        columns.append(sa.column("symbol", sa.String(length=64)))
    if "isin" in column_names:
        columns.append(sa.column("isin", sa.String(length=32)))
    if "mic" in column_names:
        columns.append(sa.column("mic", sa.String(length=16)))
    if "portfolio_type" in column_names:
        columns.append(sa.column("portfolio_type", sa.String(length=16)))
    if "type_portefeuille" in column_names:
        columns.append(sa.column("type_portefeuille", sa.String(length=16)))
    return sa.table("holdings", *columns)


def _normalize_isin(value: str) -> str:
    return value.replace(" ", "").upper()


def _is_isin_candidate(value: str) -> bool:
    candidate = _normalize_isin(value)
    return (
        len(candidate) == 12
        and candidate[:2].isalpha()
        and candidate.isalnum()
    )


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    column_info = {col["name"]: col for col in inspector.get_columns("holdings")}

    with op.batch_alter_table("holdings") as batch:
        if "type_portefeuille" in column_info and "portfolio_type" not in column_info:
            batch.alter_column(
                "type_portefeuille",
                new_column_name="portfolio_type",
                existing_type=column_info["type_portefeuille"]["type"],
                existing_nullable=column_info["type_portefeuille"]["nullable"],
            )

    inspector = sa.inspect(bind)
    column_info = {col["name"]: col for col in inspector.get_columns("holdings")}

    with op.batch_alter_table("holdings") as batch:
        if "portfolio_type" not in column_info:
            batch.add_column(sa.Column("portfolio_type", sa.String(length=16), nullable=True))
        if "symbol" not in column_info:
            batch.add_column(sa.Column("symbol", sa.String(length=64), nullable=True))
        if "isin" not in column_info:
            batch.add_column(sa.Column("isin", sa.String(length=32), nullable=True))
        if "mic" not in column_info:
            batch.add_column(sa.Column("mic", sa.String(length=16), nullable=True))

    inspector = sa.inspect(bind)
    column_info = {col["name"]: col for col in inspector.get_columns("holdings")}
    column_names = set(column_info)
    holdings = _holdings_table(column_names)

    if {"symbol_or_isin", "symbol", "isin"}.issubset(column_names):
        rows = bind.execute(
            sa.select(
                holdings.c.id,
                holdings.c.symbol_or_isin,
                holdings.c.symbol,
                holdings.c.isin,
            )
        ).all()

        for row in rows:
            raw_value = (row.symbol_or_isin or "").strip()
            if not raw_value:
                continue
            if (row.symbol and row.symbol.strip()) or (row.isin and row.isin.strip()):
                continue

            normalized = _normalize_isin(raw_value)
            if _is_isin_candidate(normalized):
                bind.execute(
                    sa.update(holdings)
                    .where(holdings.c.id == row.id)
                    .values(isin=normalized)
                )
            else:
                bind.execute(
                    sa.update(holdings)
                    .where(holdings.c.id == row.id)
                    .values(symbol=raw_value.strip())
                )

    if "portfolio_type" in column_names:
        bind.execute(
            sa.text(
                """
                UPDATE holdings
                SET portfolio_type = COALESCE(NULLIF(TRIM(portfolio_type), ''), 'PEA')
                """
            )
        )
        with op.batch_alter_table("holdings") as batch:
            batch.alter_column(
                "portfolio_type",
                existing_type=column_info["portfolio_type"]["type"],
                nullable=False,
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    column_info = {col["name"]: col for col in inspector.get_columns("holdings")}
    column_names = set(column_info)
    holdings = _holdings_table(column_names)

    if {"symbol_or_isin", "symbol", "isin"}.issubset(column_names):
        bind.execute(
            sa.text(
                """
                UPDATE holdings
                SET symbol_or_isin = CASE
                    WHEN isin IS NOT NULL AND TRIM(isin) != '' THEN isin
                    WHEN symbol IS NOT NULL AND TRIM(symbol) != '' THEN symbol
                    ELSE symbol_or_isin
                END
                """
            )
        )
        bind.execute(sa.text("UPDATE holdings SET symbol = NULL"))
        bind.execute(sa.text("UPDATE holdings SET isin = NULL"))

    with op.batch_alter_table("holdings") as batch:
        if "portfolio_type" in column_info and column_info["portfolio_type"]["nullable"]:
            batch.alter_column(
                "portfolio_type",
                existing_type=column_info["portfolio_type"]["type"],
                nullable=True,
            )
        if "mic" in column_names:
            batch.drop_column("mic")
        if "isin" in column_names:
            batch.drop_column("isin")
        if "symbol" in column_names:
            batch.drop_column("symbol")
        if "portfolio_type" in column_names and "type_portefeuille" not in column_names:
            batch.alter_column(
                "portfolio_type",
                new_column_name="type_portefeuille",
                existing_type=column_info["portfolio_type"]["type"],
            )
        elif "portfolio_type" in column_names:
            batch.drop_column("portfolio_type")
