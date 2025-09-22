from __future__ import annotations

import csv
import io
import zipfile
from datetime import datetime
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
        "type_portefeuille",
        "operation",
        "asset",
        "symbol_or_isin",
        "quantity",
        "unit_price_eur",
        "fee_eur",
        "fee_asset",
        "fx_rate",
        "total_eur",
        "ts",
        "notes",
        "external_ref",
    ],
    "holdings.csv": [
        "as_of",
        "type_portefeuille",
        "asset",
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


def _write_transactions(db: Session, zf: zipfile.ZipFile) -> None:
    rows = db.query(Transaction).order_by(Transaction.ts).all()
    _write_csv(zf, "transactions.csv", CSV_FILES["transactions.csv"], [
        [
            row.id,
            row.source,
            row.type_portefeuille,
            row.operation,
            row.asset,
            row.symbol_or_isin,
            row.quantity,
            row.unit_price_eur,
            row.fee_eur,
            row.fee_asset,
            row.fx_rate,
            row.total_eur,
            row.ts.isoformat(),
            row.notes,
            row.external_ref,
        ]
        for row in rows
    ])


def _write_holdings(db: Session, zf: zipfile.ZipFile) -> None:
    rows = db.query(Holding).order_by(Holding.as_of.desc()).all()
    _write_csv(zf, "holdings.csv", CSV_FILES["holdings.csv"], [
        [
            row.as_of.isoformat(),
            row.type_portefeuille,
            row.asset,
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
