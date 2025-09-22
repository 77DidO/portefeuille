from __future__ import annotations

import logging
import re
from typing import Dict, Tuple

import httpx
from cachetools import TTLCache

from app.db.session import SessionLocal
from app.services.system_logs import record_log

__all__ = [
    "EuronextAPIError",
    "fetch_price",
    "search_instrument_by_isin",
    "search_instrument_by_symbol",
    "lookup_instrument_by_isin",
    "clear_cache",
]

_API_URL = "https://live.euronext.com/en/ajax/getLiveData/issue"
_CACHE: TTLCache[str, float] = TTLCache(maxsize=256, ttl=300)
_LOOKUP_URL = "https://live.euronext.com/en/ajax/getListingByIsin"
_LOOKUP_CACHE: TTLCache[str, Tuple[str, str]] = TTLCache(maxsize=256, ttl=300)
_SEARCH_URL = "https://live.euronext.com/en/ajax/search"
_SEARCH_CACHE: TTLCache[str, Tuple[str, str]] = TTLCache(maxsize=256, ttl=300)
_SYMBOL_SEARCH_CACHE: TTLCache[str, Tuple[str, str]] = TTLCache(maxsize=256, ttl=300)
_EURONEXT_MICS = {
    "XPAR",
    "XAMS",
    "XBRU",
    "XLIS",
    "XMIL",
    "XDUB",
}


logger = logging.getLogger(__name__)
_ISSUE_REGEX = re.compile(
    r"^(?P<symbol>[A-Z0-9]+)-(?P<isin>[A-Z]{2}[A-Z0-9]{9}[0-9])-(?P<mic>X[A-Z0-9]{3})$"
)
_ISIN_REGEX = re.compile(r"^[A-Z]{2}[A-Z0-9]{9}[0-9]$")


class EuronextAPIError(RuntimeError):
    """Raised when fetching data from Euronext fails."""


def _record_euronext_log(level: str, message: str, meta: Dict[str, object] | None = None) -> None:
    log_level = logging._nameToLevel.get(level.upper(), logging.INFO)
    logger.log(log_level, message)

    try:
        with SessionLocal() as db:
            record_log(db, level.upper(), "euronext", message, meta=meta)
    except Exception as exc:  # pragma: no cover - logging should not disrupt processing
        logger.warning(
            "Failed to record Euronext system log: %s",
            exc,
            extra={"meta": meta},
        )


def _normalize(value: str | None) -> str:
    return (value or "").strip().upper()


def _extract_lookup_candidates(payload: object) -> Tuple[Dict[str, object], ...]:
    if isinstance(payload, dict):
        for key in ("data", "results", "rows", "items"):
            nested = payload.get(key)
            if isinstance(nested, list):
                return tuple(item for item in nested if isinstance(item, dict))
        return (payload,)
    if isinstance(payload, list):
        return tuple(item for item in payload if isinstance(item, dict))
    return tuple()


def search_instrument_by_isin(isin: str) -> Tuple[str, str]:
    normalized = _normalize(isin)
    if not normalized:
        raise EuronextAPIError("Missing ISIN for Euronext search")
    if not _ISIN_REGEX.match(normalized):
        raise EuronextAPIError(f"Invalid ISIN '{isin}' for Euronext search")

    try:
        return _SEARCH_CACHE[normalized]
    except KeyError:
        pass

    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(_SEARCH_URL, params={"search": normalized})
            response.raise_for_status()
            payload = response.json()
    except httpx.HTTPError as exc:
        raise EuronextAPIError(f"Euronext search failed for '{normalized}'") from exc
    except ValueError as exc:
        raise EuronextAPIError("Invalid JSON received from Euronext search") from exc

    for candidate in _extract_lookup_candidates(payload):
        candidate_isin = _normalize(candidate.get("isin"))
        if candidate_isin and candidate_isin != normalized:
            continue
        symbol = _normalize(candidate.get("symbol"))
        if not symbol:
            symbol = _normalize(candidate.get("mnemonic"))
        mic = _normalize(candidate.get("mic"))
        if not mic:
            mic = _normalize(candidate.get("market"))
        if not mic:
            mic = _normalize(candidate.get("micCode"))
        if mic and mic not in _EURONEXT_MICS:
            mic = _normalize(candidate.get("isoMic"))
        if symbol and mic and mic in _EURONEXT_MICS:
            result = (symbol, mic)
            _SEARCH_CACHE[normalized] = result
            return result

    raise EuronextAPIError(f"Euronext search returned no instrument for '{normalized}'")


def search_instrument_by_symbol(symbol: str, mic: str | None) -> Tuple[str, str]:
    normalized_symbol = _normalize(symbol)
    if not normalized_symbol:
        raise EuronextAPIError("Missing symbol for Euronext search")

    normalized_mic = _normalize(mic) if mic else ""
    if normalized_mic and normalized_mic not in _EURONEXT_MICS:
        raise EuronextAPIError(f"Unknown Euronext market '{mic}' for symbol search")

    cache_key = (
        f"{normalized_symbol}-{normalized_mic}" if normalized_mic else normalized_symbol
    )

    try:
        return _SYMBOL_SEARCH_CACHE[cache_key]
    except KeyError:
        pass

    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(_SEARCH_URL, params={"search": normalized_symbol})
            response.raise_for_status()
            payload = response.json()
    except httpx.HTTPError as exc:
        raise EuronextAPIError(
            f"Euronext search failed for symbol '{normalized_symbol}'"
        ) from exc
    except ValueError as exc:
        raise EuronextAPIError("Invalid JSON received from Euronext search") from exc

    for candidate in _extract_lookup_candidates(payload):
        candidate_symbol = _normalize(candidate.get("symbol"))
        if not candidate_symbol:
            candidate_symbol = _normalize(candidate.get("mnemonic"))
        if not candidate_symbol or candidate_symbol != normalized_symbol:
            continue

        candidate_mic = _normalize(candidate.get("mic"))
        if not candidate_mic:
            candidate_mic = _normalize(candidate.get("market"))
        if not candidate_mic:
            candidate_mic = _normalize(candidate.get("micCode"))
        if candidate_mic and candidate_mic not in _EURONEXT_MICS:
            candidate_mic = _normalize(candidate.get("isoMic"))

        if normalized_mic and candidate_mic and candidate_mic != normalized_mic:
            continue
        if normalized_mic and not candidate_mic:
            candidate_mic = normalized_mic

        if not candidate_mic or candidate_mic not in _EURONEXT_MICS:
            continue

        candidate_isin = _normalize(candidate.get("isin"))
        if not candidate_isin or not _ISIN_REGEX.match(candidate_isin):
            continue

        result = (candidate_isin, candidate_mic)
        _SYMBOL_SEARCH_CACHE[cache_key] = result
        return result

    raise EuronextAPIError(
        f"Euronext search returned no instrument for symbol '{normalized_symbol}'"
    )


def lookup_instrument_by_isin(isin: str) -> Tuple[str, str]:
    normalized = _normalize(isin)
    if not normalized:
        raise EuronextAPIError("Missing ISIN for Euronext lookup")
    if not _ISIN_REGEX.match(normalized):
        raise EuronextAPIError(f"Invalid ISIN '{isin}' for Euronext lookup")

    try:
        return _LOOKUP_CACHE[normalized]
    except KeyError:
        pass

    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(_LOOKUP_URL, params={"isin": normalized})
            response.raise_for_status()
            payload = response.json()
    except httpx.HTTPError as exc:
        raise EuronextAPIError(f"Euronext lookup failed for '{normalized}'") from exc
    except ValueError as exc:
        raise EuronextAPIError("Invalid JSON received from Euronext lookup") from exc

    for candidate in _extract_lookup_candidates(payload):
        symbol = _normalize(candidate.get("symbol"))
        if not symbol:
            symbol = _normalize(candidate.get("mnemonic"))
        mic = _normalize(candidate.get("mic"))
        if not mic:
            mic = _normalize(candidate.get("market"))
        if not mic:
            mic = _normalize(candidate.get("micCode"))
        if symbol and mic:
            if mic not in _EURONEXT_MICS:
                mic = _normalize(candidate.get("isoMic"))
            if mic in _EURONEXT_MICS:
                result = (symbol, mic)
                _LOOKUP_CACHE[normalized] = result
                return result

    raise EuronextAPIError(f"Euronext lookup returned no instrument for '{normalized}'")


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
    request_meta = {
        "identifier": identifier,
        "normalized": normalized,
        "url": _API_URL,
        "params": params,
    }
    _record_euronext_log(
        "INFO",
        f"Requesting Euronext price for {normalized} at {_API_URL}",
        request_meta,
    )

    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(_API_URL, params=params)
            response.raise_for_status()
            payload = response.json()
    except httpx.HTTPStatusError as exc:
        error_meta = {**request_meta, "status_code": exc.response.status_code}
        _record_euronext_log(
            "WARNING",
            f"Euronext HTTP error {exc.response.status_code} for {normalized}",
            error_meta,
        )
        raise EuronextAPIError(f"Euronext request failed for '{normalized}'") from exc
    except httpx.HTTPError as exc:
        _record_euronext_log(
            "ERROR",
            f"Euronext request failed for {normalized}: {exc}",
            request_meta,
        )
        raise EuronextAPIError(f"Euronext request failed for '{normalized}'") from exc
    except ValueError as exc:
        _record_euronext_log(
            "ERROR",
            f"Invalid JSON received from Euronext for {normalized}",
            request_meta,
        )
        raise EuronextAPIError("Invalid JSON received from Euronext") from exc

    price_value = _extract_price(payload)
    success_meta = {**request_meta, "price": price_value}
    _record_euronext_log(
        "INFO",
        f"Euronext price for {normalized} is {price_value}",
        success_meta,
    )

    _CACHE[normalized] = price_value
    _CACHE[cache_key] = price_value
    for alias in aliases:
        _CACHE[alias] = price_value
    return price_value


def clear_cache() -> None:
    """Clear the internal TTL cache (used in tests)."""

    _CACHE.clear()
    _LOOKUP_CACHE.clear()
    _SEARCH_CACHE.clear()
    _SYMBOL_SEARCH_CACHE.clear()
