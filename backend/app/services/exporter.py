from __future__ import annotations

import csv
import io
import zipfile
from datetime import datetime, timezone
from decimal import Decimal
from typing import Iterable, Tuple

from sqlalchemy.orm import Session

from app.models.holdings import Holding
from app.models.journal_trades import JournalTrade
from app.models.snapshots import Snapshot
from app.models.transactions import Transaction


CSV_FILES = {
    "transactions.csv": [
        "id",
        "source",
        "portfolio_type",
        "operation",
        "date",
        "asset",
        "symbol",
        "isin",
        "mic",
        "quantity",
        "unit_price_eur",
        "total_eur",
        "fee_eur",
        "fee_asset",
        "fee_quantity",
        "notes",
    ],
    "holdings.csv": [
        "snapshot_id",
        "as_of",
        "portfolio_type",
        "asset",
        "symbol",
        "isin",
        "mic",
        "symbol_or_isin",
        "quantity",
        "pru_eur",
        "invested_eur",
        "market_price_eur",
        "market_value_eur",
        "pl_eur",
        "pl_pct",
    ],
    "snapshots.csv": [
        "ts",
        "value_pea_eur",
        "value_crypto_eur",
        "value_total_eur",
        "pnl_total_eur",
    ],
    "journal_trades.csv": [
        "id",
        "asset",
        "pair",
        "setup",
        "entry",
        "sl",
        "tp",
        "risk_r",
        "status",
        "opened_at",
        "closed_at",
        "result_r",
        "notes",
    ],
}


def export_zip(db: Session) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        _write_transactions(db, zf)
        _write_holdings(db, zf)
        _write_snapshots(db, zf)
        _write_journal(db, zf)
    buffer.seek(0)
    return buffer.read()


def _format_decimal(value: float | None) -> str:
    if value is None:
        return ""
    dec = Decimal(str(value))
    formatted = format(dec.normalize(), "f")
    if "." in formatted:
        formatted = formatted.rstrip("0").rstrip(".")
    return formatted


def _format_datetime(value: datetime) -> str:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _write_transactions(db: Session, zf: zipfile.ZipFile) -> None:
    rows = db.query(Transaction).order_by(Transaction.trade_date).all()
    _write_csv(zf, "transactions.csv", CSV_FILES["transactions.csv"], [
        [
            row.transaction_uid,
            row.source,
            row.portfolio_type,
            row.operation,
            _format_datetime(row.trade_date),
            row.asset,
            row.symbol or "",
            row.isin or "",
            row.mic or "",
            _format_decimal(row.quantity),
            _format_decimal(row.unit_price_eur),
            _format_decimal(row.total_eur),
            _format_decimal(row.fee_eur),
            row.fee_asset or "",
            _format_decimal(row.fee_quantity),
            row.notes or "",
        ]
        for row in rows
    ])


def _write_holdings(db: Session, zf: zipfile.ZipFile) -> None:
    rows = (
        db.query(Holding)
        .join(Holding.snapshot)
        .order_by(Snapshot.ts.desc(), Holding.id)
        .all()
    )
    _write_csv(zf, "holdings.csv", CSV_FILES["holdings.csv"], [
        [
            row.snapshot_id,
            row.as_of.isoformat(),
            row.portfolio_type,
            row.asset,
            row.symbol or "",
            row.isin or "",
            row.mic or "",
            row.symbol_or_isin,
            row.quantity,
            row.pru_eur,
            row.invested_eur,
            row.market_price_eur,
            row.market_value_eur,
            row.pl_eur,
            row.pl_pct,
        ]
        for row in rows
    ])


def _write_snapshots(db: Session, zf: zipfile.ZipFile) -> None:
    rows = db.query(Snapshot).order_by(Snapshot.ts).all()
    _write_csv(zf, "snapshots.csv", CSV_FILES["snapshots.csv"], [
        [
            row.ts.isoformat(),
            row.value_pea_eur,
            row.value_crypto_eur,
            row.value_total_eur,
            row.pnl_total_eur,
        ]
        for row in rows
    ])


def _write_journal(db: Session, zf: zipfile.ZipFile) -> None:
    rows = db.query(JournalTrade).order_by(JournalTrade.id).all()
    _write_csv(zf, "journal_trades.csv", CSV_FILES["journal_trades.csv"], [
        [
            row.id,
            row.asset,
            row.pair,
            row.setup,
            row.entry,
            row.sl,
            row.tp,
            row.risk_r,
            row.status,
            row.opened_at.isoformat() if row.opened_at else "",
            row.closed_at.isoformat() if row.closed_at else "",
            row.result_r,
            row.notes,
        ]
        for row in rows
    ])


def _write_csv(zf: zipfile.ZipFile, name: str, headers: Iterable[str], rows: Iterable[Iterable]) -> None:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(headers)
    for row in rows:
        writer.writerow(row)
    zf.writestr(name, buffer.getvalue())
