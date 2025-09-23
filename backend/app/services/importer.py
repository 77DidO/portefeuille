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
    ]
}

TRANSACTION_UID_FIELDS = [
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
]

TRANSACTION_UID_SEPARATOR = "\x1f"

FUNCTIONAL_TRANSACTION_FIELDS = [
    "source",
    "portfolio_type",
    "operation",
    "asset",
    "symbol",
    "isin",
    "mic",
    "quantity",
    "unit_price_eur",
    "fee_eur",
    "fee_asset",
    "fee_quantity",
    "total_eur",
    "trade_date",
    "notes",
]

TRANSACTION_FIELD_MAPPING = {
    "source": "source",
    "portfolio_type": "portfolio_type",
    "operation": "operation",
    "asset": "asset",
    "symbol": "symbol",
    "isin": "isin",
    "mic": "mic",
    "quantity": "quantity",
    "unit_price_eur": "unit_price_eur",
    "fee_eur": "fee_eur",
    "fee_asset": "fee_asset",
    "fee_quantity": "fee_quantity",
    "total_eur": "total_eur",
    "trade_date": "trade_date",
    "notes": "notes",
}


def _clean_text(value: str | None) -> str:
    return value.strip() if value is not None else ""


def _normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    text = value.strip()
    if not text:
        return None
    if text.casefold() == "none":
        return None
    return text


def _normalize_optional_text_to_string(value: str | None) -> str:
    normalized = _normalize_optional_text(value)
    return normalized if normalized is not None else ""


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
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:  # pragma: no cover - converted to ImportErrorDetail
        raise ValueError(f"Valeur de date invalide pour {field}: {value!r}") from exc
    return to_utc(parsed)


def _parse_optional_decimal(value: str | None) -> Decimal | None:
    text = _clean_text(value)
    if not text:
        return None
    try:
        return Decimal(text)
    except InvalidOperation as exc:  # pragma: no cover - converted to ImportErrorDetail
        raise ValueError(f"Valeur décimale invalide: {value!r}") from exc


def _decimal_to_string(value: Decimal) -> str:
    formatted = format(value.normalize(), "f")
    if "." in formatted:
        formatted = formatted.rstrip("0").rstrip(".")
    return formatted


def _build_normalized_transaction_uid_fields(
    *,
    row_id: str | None,
    source: str,
    portfolio_type: str,
    operation: str,
    asset: str,
    symbol: str | None,
    isin: str | None,
    mic: str | None,
    quantity: Decimal,
    unit_price_eur: Decimal,
    total_eur: Decimal,
    fee_eur: Decimal,
    fee_asset: str,
    fee_quantity: Decimal | None,
    trade_date: datetime,
    notes: str,
) -> Dict[str, str]:
    normalized: Dict[str, str] = {
        "id": row_id or "",
        "source": source,
        "portfolio_type": portfolio_type,
        "operation": operation,
        "date": trade_date.isoformat(),
        "asset": asset,
        "symbol": symbol or "",
        "isin": isin or "",
        "mic": mic or "",
        "quantity": _decimal_to_string(quantity),
        "unit_price_eur": _decimal_to_string(unit_price_eur),
        "total_eur": _decimal_to_string(total_eur),
        "fee_eur": _decimal_to_string(fee_eur),
        "fee_asset": fee_asset,
        "fee_quantity": _decimal_to_string(fee_quantity) if fee_quantity is not None else "",
        "notes": notes,
    }
    return normalized


def _prepare_row_for_transaction_uid(
    row: Dict[str, str]
) -> Tuple[
    Dict[str, str],
    Decimal,
    Decimal,
    Decimal,
    Decimal,
    str,
    Decimal | None,
    datetime,
    str | None,
    str | None,
    str | None,
    str | None,
    str,
]:
    row_id = _normalize_optional_text(row.get("id"))
    source = _parse_required_text(row.get("source"), "source")
    portfolio_type = _parse_required_text(row.get("portfolio_type"), "portfolio_type")
    operation = _parse_required_text(row.get("operation"), "operation")
    asset = _parse_required_text(row.get("asset"), "asset")
    symbol = _normalize_optional_text(row.get("symbol"))
    isin = _normalize_optional_text(row.get("isin"))
    mic = _normalize_optional_text(row.get("mic"))
    quantity = _parse_decimal_field(row.get("quantity"), default=None, field="quantity")
    unit_price_eur = _parse_decimal_field(
        row.get("unit_price_eur"),
        default=None,
        field="unit_price_eur",
    )
    fee_eur = _parse_decimal_field(row.get("fee_eur"), default=Decimal("0"), field="fee_eur")
    total_eur = _parse_decimal_field(row.get("total_eur"), default=None, field="total_eur")
    fee_asset = _normalize_optional_text_to_string(row.get("fee_asset"))
    fee_quantity = _parse_optional_decimal(row.get("fee_quantity"))
    trade_date = _parse_timestamp(row.get("date"), field="date")
    notes = _normalize_optional_text_to_string(row.get("notes"))
    normalized_fields = _build_normalized_transaction_uid_fields(
        row_id=row_id,
        source=source,
        portfolio_type=portfolio_type,
        operation=operation,
        asset=asset,
        symbol=symbol,
        isin=isin,
        mic=mic,
        quantity=quantity,
        unit_price_eur=unit_price_eur,
        total_eur=total_eur,
        fee_eur=fee_eur,
        fee_asset=fee_asset,
        fee_quantity=fee_quantity,
        trade_date=trade_date,
        notes=notes,
    )
    return (
        normalized_fields,
        quantity,
        unit_price_eur,
        fee_eur,
        total_eur,
        fee_asset,
        fee_quantity,
        trade_date,
        symbol,
        isin,
        mic,
        notes,
        row_id,
    )


def build_transaction_uid(row_id: str | None, normalized_fields: Mapping[str, str]) -> str:
    """Return an explicit identifier or generate a deterministic one for a CSV row."""

    normalized_id = _normalize_optional_text(row_id)
    if normalized_id:
        return normalized_id

    missing = [field for field in TRANSACTION_UID_FIELDS if field not in normalized_fields]
    if missing:
        raise ValueError(
            "Champs manquants pour générer transaction_uid: " + ", ".join(missing)
        )

    payload = TRANSACTION_UID_SEPARATOR.join(
        normalized_fields[field] for field in TRANSACTION_UID_FIELDS
    )
    digest = hashlib.sha1(payload.encode("utf-8")).hexdigest()
    return f"import_{digest}"


def compute_transaction_uid_from_row(row: Dict[str, str]) -> str:
    """Compute the transaction UID for a CSV row, normalising its values if needed."""

    normalized_fields, *_, row_id = _prepare_row_for_transaction_uid(row)
    return build_transaction_uid(row_id, normalized_fields)


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

    def _find_identical_transaction(self, data: Mapping[str, object]) -> Transaction | None:
        filters = {
            TRANSACTION_FIELD_MAPPING[field]: data.get(field)
            for field in FUNCTIONAL_TRANSACTION_FIELDS
        }
        return self.db.query(Transaction).filter_by(**filters).one_or_none()

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
        if not reader.fieldnames:
            raise ImportErrorDetail("En-tête CSV manquant")
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
                    total_eur,
                    fee_asset,
                    fee_quantity,
                    trade_date,
                    symbol,
                    isin,
                    mic,
                    notes,
                    row_id,
                ) = _prepare_row_for_transaction_uid(row)
                transaction_uid = build_transaction_uid(row_id, normalized_fields)
                lookup_data = {
                    "source": normalized_fields["source"],
                    "portfolio_type": normalized_fields["portfolio_type"],
                    "operation": normalized_fields["operation"],
                    "asset": normalized_fields["asset"],
                    "symbol": symbol,
                    "isin": isin,
                    "mic": mic,
                    "quantity": float(quantity),
                    "unit_price_eur": float(unit_price_eur),
                    "fee_eur": float(fee_eur),
                    "fee_asset": fee_asset or None,
                    "fee_quantity": float(fee_quantity) if fee_quantity is not None else None,
                    "total_eur": float(total_eur),
                    "trade_date": trade_date,
                    "notes": _normalize_optional_text(notes) if notes else None,
                }
                data = {
                    "source": lookup_data["source"],
                    "portfolio_type": normalized_fields["portfolio_type"],
                    "operation": lookup_data["operation"],
                    "asset": lookup_data["asset"],
                    "symbol": symbol,
                    "isin": isin,
                    "mic": mic,
                    "symbol_or_isin": symbol or isin or None,
                    "quantity": lookup_data["quantity"],
                    "unit_price_eur": lookup_data["unit_price_eur"],
                    "fee_eur": lookup_data["fee_eur"],
                    "fee_asset": lookup_data["fee_asset"],
                    "fee_quantity": lookup_data["fee_quantity"],
                    "total_eur": lookup_data["total_eur"],
                    "trade_date": trade_date,
                    "notes": lookup_data["notes"],
                    "transaction_uid": transaction_uid,
                }
            except Exception as exc:  # noqa: BLE001
                raise ImportErrorDetail(str(exc), row_number=idx) from exc

            existing = (
                self.db.query(Transaction)
                .filter(Transaction.transaction_uid == transaction_uid)
                .one_or_none()
            )

            if existing:
                for field, value in data.items():
                    setattr(existing, field, value)
            else:
                identical = self._find_identical_transaction(lookup_data)
                if identical:
                    for field, value in data.items():
                        setattr(identical, field, value)
                else:
                    self.db.add(Transaction(**data))
        self.db.commit()
