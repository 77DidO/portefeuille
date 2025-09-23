"""Normalize persisted transaction instrument fields.

Revision ID: 0006
Revises: 0005
Create Date: 2025-02-15 00:00:00.000000
"""

from __future__ import annotations

import re
from typing import Iterable, Tuple

from alembic import op
import sqlalchemy as sa


revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


_EURONEXT_SUFFIX_TO_MIC = {
    "PA": "XPAR",
    "PAR": "XPAR",
    "AS": "XAMS",
    "AMS": "XAMS",
    "BR": "XBRU",
    "BRU": "XBRU",
    "LS": "XLIS",
    "LIS": "XLIS",
    "MI": "XMIL",
    "MIL": "XMIL",
    "IR": "XDUB",
    "DU": "XDUB",
}
_EURONEXT_MICS = set(_EURONEXT_SUFFIX_TO_MIC.values())

_ISIN_REGEX = re.compile(r"^[A-Z]{2}[A-Z0-9]{9}[0-9]$")
_EURONEXT_COMBINED_PATTERN = re.compile(
    r"^(?P<symbol>[A-Z0-9]+)[-_/](?P<isin>[A-Z]{2}[A-Z0-9]{9}[0-9])(?:[-_/](?P<mic>[A-Z0-9]{2,4}))?$"
)
_EURONEXT_ISIN_MARKET_PATTERN = re.compile(
    r"^(?P<isin>[A-Z]{2}[A-Z0-9]{9}[0-9])[-_/](?P<mic>[A-Z0-9]{2,4})$"
)
_EURONEXT_ISSUE_PATTERN = re.compile(
    r"^(?P<symbol>[A-Z0-9]+)[-_/](?P<isin>[A-Z]{2}[A-Z0-9]{9}[0-9])[-_/](?P<mic>X[A-Z0-9]{3})$"
)


def _transactions_table(column_names: Iterable[str]) -> sa.Table:
    columns = [sa.column("id", sa.Integer)]
    optional_columns = {
        "symbol_or_isin": sa.String(length=64),
        "symbol": sa.String(length=64),
        "isin": sa.String(length=32),
        "mic": sa.String(length=16),
        "transaction_uid": sa.String(length=128),
        "portfolio_type": sa.String(length=16),
        "trade_date": sa.DateTime(timezone=True),
        "created_at": sa.DateTime(timezone=True),
        "ts": sa.DateTime(timezone=True),
    }
    for name, column_type in optional_columns.items():
        if name in column_names:
            columns.append(sa.column(name, column_type))
    return sa.table("transactions", *columns)


def _normalize_symbol(value: str | None) -> str | None:
    if not value:
        return None
    normalized = value.strip().upper()
    return normalized or None


def _normalize_isin(value: str | None) -> str | None:
    if not value:
        return None
    normalized = value.replace(" ", "").upper()
    if _ISIN_REGEX.match(normalized):
        return normalized
    return None


def _normalize_mic(value: str | None) -> str | None:
    if not value:
        return None
    upper = value.strip().upper()
    if not upper:
        return None
    if upper in _EURONEXT_MICS or (len(upper) == 4 and upper.startswith("X")):
        return upper
    return _EURONEXT_SUFFIX_TO_MIC.get(upper) or upper


def _extract_symbol_mic(candidate: str) -> Tuple[str, str] | None:
    for separator in ("-", ".", ":", "@", "/"):
        if separator in candidate:
            base, suffix = candidate.rsplit(separator, 1)
            base = base.strip().upper()
            mic = _normalize_mic(suffix)
            if base and mic:
                return base, mic
    return None


def _parse_symbol_or_isin(raw_value: str | None) -> Tuple[str | None, str | None, str | None]:
    if not raw_value:
        return None, None, None
    normalized = raw_value.strip().upper()
    if not normalized:
        return None, None, None

    issue_match = _EURONEXT_ISSUE_PATTERN.match(normalized)
    if issue_match:
        symbol = issue_match.group("symbol")
        isin = issue_match.group("isin")
        mic = _normalize_mic(issue_match.group("mic"))
        return symbol, isin, mic

    combined_match = _EURONEXT_COMBINED_PATTERN.match(normalized)
    if combined_match:
        symbol = combined_match.group("symbol")
        isin = combined_match.group("isin")
        mic = _normalize_mic(combined_match.group("mic"))
        return symbol, isin, mic

    isin_market_match = _EURONEXT_ISIN_MARKET_PATTERN.match(normalized)
    if isin_market_match:
        isin = isin_market_match.group("isin")
        mic = _normalize_mic(isin_market_match.group("mic"))
        return None, isin, mic

    if _ISIN_REGEX.match(normalized):
        return None, normalized, None

    symbol_mic = _extract_symbol_mic(normalized)
    if symbol_mic:
        return symbol_mic[0], None, symbol_mic[1]

    return normalized, None, None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    column_info = {col["name"]: col for col in inspector.get_columns("transactions")}
    column_names = set(column_info)
    transactions = _transactions_table(column_names)

    if "portfolio_type" in column_names:
        bind.execute(
            sa.text(
                """
                UPDATE transactions
                SET portfolio_type = COALESCE(NULLIF(UPPER(TRIM(portfolio_type)), ''), 'PEA')
                """
            )
        )

    if "trade_date" in column_names:
        if "created_at" in column_names:
            bind.execute(
                sa.text(
                    """
                    UPDATE transactions
                    SET trade_date = created_at
                    WHERE trade_date IS NULL AND created_at IS NOT NULL
                    """
                )
            )
        if "ts" in column_names:
            bind.execute(
                sa.text(
                    """
                    UPDATE transactions
                    SET trade_date = ts
                    WHERE trade_date IS NULL AND ts IS NOT NULL
                    """
                )
            )
        bind.execute(
            sa.text(
                """
                UPDATE transactions
                SET trade_date = CURRENT_TIMESTAMP
                WHERE trade_date IS NULL
                """
            )
        )

    if "transaction_uid" in column_names:
        rows = bind.execute(
            sa.select(transactions.c.id, transactions.c.transaction_uid)
        ).all()
        for row in rows:
            current_uid = (row.transaction_uid or "").strip()
            updated_uid = current_uid or f"legacy-tx-{row.id}"
            if updated_uid != row.transaction_uid:
                bind.execute(
                    sa.update(transactions)
                    .where(transactions.c.id == row.id)
                    .values(transaction_uid=updated_uid)
                )

    if {"symbol_or_isin", "symbol", "isin", "mic"}.issubset(column_names):
        rows = bind.execute(
            sa.select(
                transactions.c.id,
                transactions.c.symbol_or_isin,
                transactions.c.symbol,
                transactions.c.isin,
                transactions.c.mic,
            )
        ).all()
        for row in rows:
            updates: dict[str, str | None] = {}
            raw_symbol = (row.symbol or "").strip()
            raw_isin = (row.isin or "").strip()
            raw_mic = (row.mic or "").strip()

            normalized_symbol = _normalize_symbol(raw_symbol)
            normalized_isin = _normalize_isin(raw_isin)
            normalized_mic = _normalize_mic(raw_mic)

            if normalized_symbol and normalized_symbol != raw_symbol:
                updates["symbol"] = normalized_symbol
                normalized_symbol = updates["symbol"]

            if normalized_isin and normalized_isin != raw_isin:
                updates["isin"] = normalized_isin
                normalized_isin = updates["isin"]

            if normalized_mic and normalized_mic != raw_mic:
                updates["mic"] = normalized_mic
                normalized_mic = updates["mic"]
            elif raw_mic and not normalized_mic:
                updates["mic"] = raw_mic.strip().upper()
                normalized_mic = updates["mic"]

            if not (normalized_symbol and normalized_isin and normalized_mic):
                fallback_symbol, fallback_isin, fallback_mic = _parse_symbol_or_isin(row.symbol_or_isin)
                if fallback_symbol and not normalized_symbol:
                    updates["symbol"] = fallback_symbol
                    normalized_symbol = fallback_symbol
                if fallback_isin and not normalized_isin:
                    updates["isin"] = fallback_isin
                    normalized_isin = fallback_isin
                if fallback_mic and not normalized_mic:
                    updates["mic"] = fallback_mic
                    normalized_mic = fallback_mic

            if updates:
                bind.execute(
                    sa.update(transactions)
                    .where(transactions.c.id == row.id)
                    .values(**updates)
                )


def downgrade() -> None:  # pragma: no cover - data normalization is not reversible
    pass
