from __future__ import annotations

from datetime import date as date_type, datetime, time, timezone
from typing import Any, Mapping, Optional

from pydantic import BaseModel, Field, ConfigDict, constr, model_validator


def _combine_date_with_time(value: date_type | datetime | None, tz: timezone | None = None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    tzinfo = tz or timezone.utc
    return datetime.combine(value, time.min, tzinfo=tzinfo)


class TransactionBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    source: str
    portfolio_type: constr(to_lower=True)
    operation: str
    asset: str
    symbol_or_isin: Optional[str]
    symbol: Optional[str] = None
    isin: Optional[str] = None
    mic: Optional[str] = None
    quantity: float
    unit_price_eur: float
    fee_eur: float
    fee_asset: Optional[str] = None
    fee_quantity: Optional[float] = None
    total_eur: float
    date: date_type = Field(..., description="Transaction date (UTC)")
    notes: Optional[str]
    csv_transaction_id: Optional[str]

    @model_validator(mode="before")
    @classmethod
    def _populate_virtual_fields(cls, data: Any) -> Mapping[str, Any]:
        if isinstance(data, Mapping):
            values = dict(data)
            raw_trade_date = data.get("trade_date")
            raw_csv_id = data.get("transaction_uid")
        else:
            values = {name: getattr(data, name) for name in cls.model_fields if hasattr(data, name)}
            raw_trade_date = getattr(data, "trade_date", None)
            raw_csv_id = getattr(data, "transaction_uid", None)

        if ("date" not in values or values["date"] is None) and raw_trade_date is not None:
            if isinstance(raw_trade_date, datetime):
                values["date"] = raw_trade_date.date()
            else:
                values["date"] = raw_trade_date

        if ("csv_transaction_id" not in values or values["csv_transaction_id"] is None) and raw_csv_id is not None:
            values["csv_transaction_id"] = raw_csv_id

        values.pop("trade_date", None)
        values.pop("transaction_uid", None)
        return values


class TransactionCreate(TransactionBase):
    pass


class TransactionResponse(TransactionBase):
    id: int


class TransactionUpdate(BaseModel):
    source: str | None = None
    portfolio_type: constr(to_lower=True) | None = None
    operation: str | None = None
    asset: str | None = None
    symbol_or_isin: Optional[str] = None
    symbol: Optional[str] = None
    isin: Optional[str] = None
    mic: Optional[str] = None
    quantity: float | None = None
    unit_price_eur: float | None = None
    fee_eur: float | None = None
    fee_asset: Optional[str] = None
    fee_quantity: Optional[float] = None
    total_eur: float | None = None
    date: date_type | datetime | None = None
    notes: Optional[str] = None
    csv_transaction_id: Optional[str] = None

    def to_orm_updates(self, current_timezone: timezone | None = None) -> dict[str, object]:
        data = self.dict(exclude_unset=True)
        updates: dict[str, object] = {}

        if "date" in data:
            updates["trade_date"] = _combine_date_with_time(
                data.pop("date"),
                current_timezone,
            )

        if "csv_transaction_id" in data:
            updates["transaction_uid"] = data.pop("csv_transaction_id")

        updates.update(data)
        return updates


class TransactionDeleteResponse(BaseModel):
    status: str
