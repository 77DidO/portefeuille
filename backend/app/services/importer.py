from __future__ import annotations

import csv
import hashlib
import io
import zipfile
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Dict, Iterable, List, Mapping, Tuple

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

EXTERNAL_REF_FIELDS = [
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

EXTERNAL_REF_SEPARATOR = "\x1f"


def _clean_text(value: str | None) -> str:
    return value.strip() if value is not None else ""


def _parse_required_text(value: str | None, field: str) -> str:
    text = _clean_text(value)
    if not text:
        raise ValueError(f"Valeur manquante pour {field}")
    return text


def _parse_decimal_field(
    value: str | None,
    *,
    default: Decimal | None,
    field: str,
) -> Decimal:
    text = _clean_text(value)
    if not text:
        if default is not None:
            return default
        raise ValueError(f"Valeur manquante pour {field}")
    try:
        return Decimal(text)
    except InvalidOperation as exc:  # pragma: no cover - converted to ImportErrorDetail
        raise ValueError(f"Valeur décimale invalide pour {field}: {value!r}") from exc


def _parse_timestamp(value: str | None, *, field: str = "ts") -> datetime:
    text = _clean_text(value)
    if not text:
        raise ValueError(f"Valeur manquante pour {field}")
    return to_utc(datetime.fromisoformat(text.replace("Z", "+00:00")))


def _decimal_to_string(value: Decimal) -> str:
    formatted = format(value.normalize(), "f")
    if "." in formatted:
        formatted = formatted.rstrip("0").rstrip(".")
    return formatted


def _build_normalized_external_ref_fields(
    row: Dict[str, str],
    *,
    quantity: Decimal,
    unit_price_eur: Decimal,
    fee_eur: Decimal,
    fee_asset: str,
    fx_rate: Decimal,
    total_eur: Decimal,
    ts: datetime,
) -> Dict[str, str]:
    return {
        "source": _parse_required_text(row.get("source"), "source"),
        "type_portefeuille": _parse_required_text(row.get("type_portefeuille"), "type_portefeuille"),
        "operation": _parse_required_text(row.get("operation"), "operation"),
        "asset": _parse_required_text(row.get("asset"), "asset"),
        "symbol_or_isin": _clean_text(row.get("symbol_or_isin")),
        "quantity": _decimal_to_string(quantity),
        "unit_price_eur": _decimal_to_string(unit_price_eur),
        "fee_eur": _decimal_to_string(fee_eur),
        "fee_asset": fee_asset,
        "fx_rate": _decimal_to_string(fx_rate),
        "total_eur": _decimal_to_string(total_eur),
        "ts": ts.isoformat(),
    }


def _prepare_row_for_external_ref(
    row: Dict[str, str]
) -> Tuple[Dict[str, str], Decimal, Decimal, Decimal, Decimal, Decimal, str, datetime]:
    fee_asset = _clean_text(row.get("fee_asset"))
    quantity = _parse_decimal_field(row.get("quantity"), default=None, field="quantity")
    unit_price_eur = _parse_decimal_field(
        row.get("unit_price_eur"),
        default=None,
        field="unit_price_eur",
    )
    fee_eur = _parse_decimal_field(row.get("fee_eur"), default=Decimal("0"), field="fee_eur")
    fx_rate = _parse_decimal_field(row.get("fx_rate"), default=Decimal("1"), field="fx_rate")
    total_eur = _parse_decimal_field(row.get("total_eur"), default=None, field="total_eur")
    ts = _parse_timestamp(row.get("ts"))
    normalized_fields = _build_normalized_external_ref_fields(
        row,
        quantity=quantity,
        unit_price_eur=unit_price_eur,
        fee_eur=fee_eur,
        fee_asset=fee_asset,
        fx_rate=fx_rate,
        total_eur=total_eur,
        ts=ts,
    )
    return normalized_fields, quantity, unit_price_eur, fee_eur, fx_rate, total_eur, fee_asset, ts


def build_external_ref(existing_ref: str | None, normalized_fields: Mapping[str, str]) -> str:
    """Return an explicit reference or generate a deterministic one for a CSV row."""

    if existing_ref is not None:
        existing_ref = existing_ref.strip()
    if existing_ref:
        return existing_ref

    missing = [field for field in EXTERNAL_REF_FIELDS if field not in normalized_fields]
    if missing:
        raise ValueError(
            "Champs manquants pour générer external_ref: " + ", ".join(missing)
        )

    payload = EXTERNAL_REF_SEPARATOR.join(normalized_fields[field] for field in EXTERNAL_REF_FIELDS)
    digest = hashlib.sha1(payload.encode("utf-8")).hexdigest()
    return f"import_{digest}"


def compute_external_ref_from_row(row: Dict[str, str]) -> str:
    """Compute the external reference for a CSV row, normalising its values if needed."""

    normalized_fields, *_ = _prepare_row_for_external_ref(row)
    return build_external_ref(row.get("external_ref"), normalized_fields)


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
                (
                    normalized_fields,
                    quantity,
                    unit_price_eur,
                    fee_eur,
                    fx_rate,
                    total_eur,
                    fee_asset,
                    ts,
                ) = _prepare_row_for_external_ref(row)
                external_ref = build_external_ref(row.get("external_ref"), normalized_fields)
                data = {
                    "source": normalized_fields["source"],
                    "type_portefeuille": normalized_fields["type_portefeuille"],
                    "operation": normalized_fields["operation"],
                    "asset": normalized_fields["asset"],
                    "symbol_or_isin": normalized_fields["symbol_or_isin"] or None,
                    "quantity": float(quantity),
                    "unit_price_eur": float(unit_price_eur),
                    "fee_eur": float(fee_eur),
                    "fee_asset": fee_asset or None,
                    "fx_rate": float(fx_rate),
                    "total_eur": float(total_eur),
                    "ts": ts,
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
