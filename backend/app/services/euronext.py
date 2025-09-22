from __future__ import annotations

import re
from typing import Dict, Tuple

import httpx
from cachetools import TTLCache

__all__ = ["EuronextAPIError", "fetch_price", "clear_cache"]

_API_URL = "https://live.euronext.com/en/ajax/getLiveData/issue"
_CACHE: TTLCache[str, float] = TTLCache(maxsize=256, ttl=300)
_EURONEXT_MICS = {
    "XPAR",
    "XAMS",
    "XBRU",
    "XLIS",
    "XMIL",
    "XDUB",
}
_ISSUE_REGEX = re.compile(
    r"^(?P<symbol>[A-Z0-9]+)-(?P<isin>[A-Z]{2}[A-Z0-9]{9}[0-9])-(?P<mic>X[A-Z0-9]{3})$"
)


class EuronextAPIError(RuntimeError):
    """Raised when fetching data from Euronext fails."""


def _normalize(value: str | None) -> str:
    return (value or "").strip().upper()


def _resolve_params(identifier: str) -> Tuple[Dict[str, str], str, Tuple[str, ...]]:
    normalized = _normalize(identifier)
    if not normalized:
        raise EuronextAPIError("Missing Euronext identifier")

    issue_match = _ISSUE_REGEX.match(normalized)
    if not issue_match:
        raise EuronextAPIError(f"Unsupported Euronext identifier '{identifier}'")

    symbol = issue_match.group("symbol")
    isin = issue_match.group("isin")
    mic = issue_match.group("mic")

    if mic not in _EURONEXT_MICS:
        raise EuronextAPIError(f"Unknown Euronext market '{mic}' for '{identifier}'")

    issue = f"{symbol}-{isin}-{mic}"
    return {"issue": issue}, issue, ()


def _extract_price(payload: Dict[str, object]) -> float:
    data = payload.get("data") if isinstance(payload, dict) else None
    if data is None:
        data = payload

    if not isinstance(data, dict):
        raise EuronextAPIError("Unexpected Euronext payload structure")

    price = data.get("lastPrice")
    if price is None:
        price = data.get("last")
    if price is None:
        raise EuronextAPIError("Missing price in Euronext payload")

    try:
        price_value = float(price)
    except (TypeError, ValueError) as exc:  # pragma: no cover - defensive
        raise EuronextAPIError("Invalid price format in Euronext payload") from exc

    currency = data.get("currency")
    if isinstance(currency, str) and currency.strip():
        normalized_currency = currency.strip().upper()
        if normalized_currency not in {"EUR", "EURO"}:
            raise EuronextAPIError(
                f"Euronext returned unsupported currency '{currency}'"
            )

    return price_value


def fetch_price(identifier: str) -> float:
    """Return the latest price in EUR for the given Euronext issue identifier."""

    normalized = _normalize(identifier)
    if not normalized:
        raise EuronextAPIError("Missing Euronext identifier")

    try:
        return _CACHE[normalized]
    except KeyError:
        pass

    params, cache_key, aliases = _resolve_params(normalized)

    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(_API_URL, params=params)
            response.raise_for_status()
            payload = response.json()
    except httpx.HTTPError as exc:
        raise EuronextAPIError(f"Euronext request failed for '{normalized}'") from exc
    except ValueError as exc:
        raise EuronextAPIError("Invalid JSON received from Euronext") from exc

    price_value = _extract_price(payload)

    _CACHE[normalized] = price_value
    _CACHE[cache_key] = price_value
    for alias in aliases:
        _CACHE[alias] = price_value
    return price_value


def clear_cache() -> None:
    """Clear the internal TTL cache (used in tests)."""

    _CACHE.clear()
