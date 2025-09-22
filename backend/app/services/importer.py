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
        "fee_asset",
        "fx_rate",
        "total_eur",
        "ts",
    ]
}


class ImportErrorDetail(Exception):
    def __init__(self, message: str, row_number: int | None = None) -> None:
        super().__init__(message)
        self.row_number = row_number
        self._message = message

    @property
    def message(self) -> str:
        """Return the base error message without row metadata."""

        return self._message

    @property
    def detailed_message(self) -> str:
        """Return an error message including the row number when available."""

        if self.row_number is None:
            return self._message
        return f"{self._message} (ligne {self.row_number})"

    def __str__(self) -> str:  # pragma: no cover - delegated to detailed_message
        return self.detailed_message


class Importer:
    def __init__(self, db: Session) -> None:
        self.db = db

    def import_zip(self, content: bytes) -> None:
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            if "transactions.csv" not in zf.namelist():
                raise ImportErrorDetail("transactions.csv manquant")
            csv_bytes = zf.read("transactions.csv")
        self.import_transactions_csv(csv_bytes)

    def import_transactions_csv(self, content: bytes | str | io.IOBase) -> None:
        if isinstance(content, io.IOBase):
            raw_content = content.read()
        else:
            raw_content = content

        if isinstance(raw_content, str):
            csv_bytes = raw_content.encode("utf-8")
        elif isinstance(raw_content, (bytes, bytearray)):
            csv_bytes = bytes(raw_content)
        else:
            raise ImportErrorDetail("Flux CSV invalide")

        self._import_transactions(csv_bytes)

    def _import_transactions(self, csv_bytes: bytes) -> None:
        text = csv_bytes.decode("utf-8")
        reader = csv.DictReader(io.StringIO(text))
        missing = [c for c in REQUIRED_COLUMNS["transactions.csv"] if c not in reader.fieldnames]
        if missing:
            raise ImportErrorDetail(f"Colonnes manquantes: {', '.join(missing)}")

        for idx, row in enumerate(reader, start=2):
            try:
                external_ref = row.get("external_ref") or f"import_{row.get('source')}_{row.get('ts')}_{idx}"
                fee_asset_raw = row.get("fee_asset")
                fee_asset = fee_asset_raw.strip() if fee_asset_raw is not None else ""
                fx_rate_raw = row.get("fx_rate")
                fx_rate = fx_rate_raw.strip() if fx_rate_raw is not None else ""
                data = {
                    "source": row["source"],
                    "type_portefeuille": row["type_portefeuille"],
                    "operation": row["operation"],
                    "asset": row["asset"],
                    "symbol_or_isin": row.get("symbol_or_isin") or None,
                    "quantity": float(row["quantity"]),
                    "unit_price_eur": float(row["unit_price_eur"]),
                    "fee_eur": float(row["fee_eur"] or 0.0),
                    "fee_asset": fee_asset or None,
                    "fx_rate": float(fx_rate or 1.0),
                    "total_eur": float(row["total_eur"]),
                    "ts": to_utc(datetime.fromisoformat(row["ts"].replace("Z", "+00:00"))),
                    "notes": row.get("notes") or None,
                    "external_ref": external_ref,
                }
            except Exception as exc:  # noqa: BLE001
                raise ImportErrorDetail(str(exc), row_number=idx) from exc

            existing = (
                self.db.query(Transaction)
                .filter(Transaction.external_ref == external_ref)
                .one_or_none()
            )

            if existing:
                for field, value in data.items():
                    setattr(existing, field, value)
            else:
                self.db.add(Transaction(**data))
        self.db.commit()
