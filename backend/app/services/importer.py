from __future__ import annotations

import csv
import io
import zipfile
from datetime import datetime
from typing import Dict, Iterable, List

from sqlalchemy.orm import Session

from app.models.transactions import Transaction
from app.utils.time import to_utc

REQUIRED_COLUMNS = {
    "transactions.csv": [
        "source",
        "type_portefeuille",
        "operation",
        "asset",
        "symbol_or_isin",
        "quantity",
        "unit_price_eur",
        "fee_eur",
        "total_eur",
        "ts",
    ]
}


class ImportErrorDetail(Exception):
    def __init__(self, message: str, row_number: int | None = None) -> None:
        super().__init__(message)
        self.row_number = row_number


class Importer:
    def __init__(self, db: Session) -> None:
        self.db = db

    def import_zip(self, content: bytes) -> None:
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            if "transactions.csv" not in zf.namelist():
                raise ImportErrorDetail("transactions.csv manquant")
            self._import_transactions(zf.read("transactions.csv"))

    def _import_transactions(self, csv_bytes: bytes) -> None:
        text = csv_bytes.decode("utf-8")
        reader = csv.DictReader(io.StringIO(text))
        missing = [c for c in REQUIRED_COLUMNS["transactions.csv"] if c not in reader.fieldnames]
        if missing:
            raise ImportErrorDetail(f"Colonnes manquantes: {', '.join(missing)}")

        for idx, row in enumerate(reader, start=2):
            try:
                tx = Transaction(
                    source=row["source"],
                    type_portefeuille=row["type_portefeuille"],
                    operation=row["operation"],
                    asset=row["asset"],
                    symbol_or_isin=row.get("symbol_or_isin"),
                    quantity=float(row["quantity"]),
                    unit_price_eur=float(row["unit_price_eur"]),
                    fee_eur=float(row["fee_eur"] or 0.0),
                    total_eur=float(row["total_eur"]),
                    ts=to_utc(datetime.fromisoformat(row["ts"].replace("Z", "+00:00"))),
                    notes=row.get("notes"),
                    external_ref=row.get("external_ref") or f"import_{row.get('source')}_{row.get('ts')}_{idx}",
                )
            except Exception as exc:  # noqa: BLE001
                raise ImportErrorDetail(str(exc), row_number=idx) from exc
            self.db.add(tx)
        self.db.commit()
