from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
import json
import re
from typing import Dict, List, Tuple

import httpx

from cachetools import TTLCache, cached
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models.transactions import Transaction
from app.models.settings import Setting
from app.services.fifo import FIFOPortfolio
from app.services import binance, euronext
from app.db.session import SessionLocal
from app.utils.settings_keys import QUOTE_ALIAS_SETTING_KEY
from app.utils.time import utc_now
from app.services.system_logs import record_log


logger = logging.getLogger(__name__)


@dataclass
class HoldingView:
    identifier: str
    asset: str
    symbol_or_isin: str | None
    quantity: float
    pru_eur: float
    invested_eur: float
    market_price_eur: float
    market_value_eur: float
    pl_eur: float
    pl_pct: float
    type_portefeuille: str
    as_of: datetime
    account_id: str | None = None


@dataclass
class HoldingHistoryPointView:
    ts: datetime
    quantity: float
    invested_eur: float
    market_price_eur: float
    market_value_eur: float
    pl_eur: float
    pl_pct: float
    operation: str


@dataclass
class HoldingDetailView(HoldingView):
    history: List[HoldingHistoryPointView] = field(default_factory=list)
    realized_pnl_eur: float = 0.0
    dividends_eur: float = 0.0
    history_available: bool = False


_cache = TTLCache(maxsize=1, ttl=120)
_price_cache: TTLCache[Tuple[str, str], float] = TTLCache(maxsize=128, ttl=300)
_quote_alias_cache: TTLCache[str, Dict[str, str]] = TTLCache(maxsize=1, ttl=300)


_ISIN_REGEX = re.compile(r"^[A-Z]{2}[A-Z0-9]{9}[0-9]$")
_QUOTE_ALIAS_CACHE_KEY = "aliases"
_EURONEXT_MICS = {"XPAR", "XAMS", "XBRU", "XLIS", "XMIL", "XDUB"}
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
_EURONEXT_MIC_TO_SUFFIX = {}
for suffix, mic in _EURONEXT_SUFFIX_TO_MIC.items():
    _EURONEXT_MIC_TO_SUFFIX.setdefault(mic, suffix)


class MarketPriceUnavailable(RuntimeError):
    pass


class HoldingNotFound(RuntimeError):
    pass


FIAT_CURRENCIES = {
    "EUR",
    "USD",
    "GBP",
    "CHF",
    "JPY",
    "AUD",
    "CAD",
    "SEK",
    "NOK",
    "DKK",
    "CZK",
    "PLN",
    "HUF",
    "TRY",
    "CNY",
    "HKD",
    "SGD",
    "NZD",
    "ZAR",
}


def _contains_fiat_code(text: str) -> bool:
    if not text:
        return False
    upper_text = text.upper()
    tokens = re.findall(r"[A-Z]{3}", upper_text)
    return any(token in FIAT_CURRENCIES for token in tokens)


PortfolioKey = Tuple[str, str, str]


def _record_portfolio_log(level: str, message: str, meta: Dict[str, object] | None = None) -> None:
    log_level = logging._nameToLevel.get(level.upper(), logging.INFO)
    logger.log(log_level, message)

    try:
        with SessionLocal() as db:
            record_log(db, level.upper(), "portfolio", message, meta=meta)
    except Exception as exc:  # pragma: no cover - logging must not break processing
        logger.warning(
            "Failed to record portfolio log: %s",
            exc,
            extra={"meta": meta},
        )


def _normalize_portfolio_type(value: str | None) -> str:
    normalized = (value or "").strip().upper()
    return normalized or "PEA"


def _normalize_symbol(value: str | None) -> str:
    return (value or "").strip().upper()


def _normalize_account_id(value: str | None) -> str:
    return (value or "").strip().upper()


def _make_portfolio_key(
    type_portefeuille: str | None,
    symbol: str | None,
    account_id: str | None,
) -> PortfolioKey:
    return (
        _normalize_portfolio_type(type_portefeuille),
        _normalize_symbol(symbol),
        _normalize_account_id(account_id),
    )


def _build_identifier_from_key(key: PortfolioKey) -> str:
    type_portefeuille, symbol, account_id = key
    parts = [type_portefeuille]
    if account_id:
        parts.append(account_id)
    parts.append(symbol)
    return "::".join(parts)


def _parse_identifier(identifier: str) -> Tuple[str, str | None, str | None]:
    if not identifier:
        return "", None, None

    raw_parts = identifier.split("::")
    parts = [part.strip() for part in raw_parts]

    if len(parts) >= 3:
        type_portefeuille = parts[0].upper()
        account_id = parts[1].upper() or None
        symbol = "::".join(parts[2:]).upper()
        return symbol, type_portefeuille, account_id

    if len(parts) == 2:
        type_portefeuille = parts[0].upper()
        symbol = parts[1].upper()
        return symbol, type_portefeuille, None

    return parts[0].upper(), None, None


def _fetch_equity_price(symbol: str) -> float:
    url = "https://query1.finance.yahoo.com/v7/finance/quote"
    params = {"symbols": symbol.upper()}
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(url, params=params)
            resp.raise_for_status()
            payload = resp.json()
    except httpx.HTTPError as exc:  # pragma: no cover - exercised via mocks
        raise MarketPriceUnavailable(f"Yahoo Finance request failed for {symbol}") from exc

    results = payload.get("quoteResponse", {}).get("result", [])
    if not results:
        raise MarketPriceUnavailable(f"Yahoo Finance returned no data for {symbol}")

    price = results[0].get("regularMarketPrice")
    if price is None:
        raise MarketPriceUnavailable(f"Yahoo Finance returned no price for {symbol}")

    return float(price)


def _fetch_crypto_price(symbol: str) -> float:
    pair = f"{symbol.upper()}EUR" if not symbol.upper().endswith("EUR") else symbol.upper()

    try:
        return asyncio.run(binance.fetch_price(pair))
    except RuntimeError:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(binance.fetch_price(pair))
        finally:  # pragma: no cover - not triggered under normal tests
            loop.close()
    except Exception as exc:  # pragma: no cover - exercised via mocks
        raise MarketPriceUnavailable(f"Binance price fetch failed for {symbol}") from exc


def _load_quote_aliases() -> Dict[str, str]:
    try:
        return _quote_alias_cache[_QUOTE_ALIAS_CACHE_KEY]
    except KeyError:
        pass

    aliases: Dict[str, str] = {}
    with SessionLocal() as db:
        setting = db.get(Setting, QUOTE_ALIAS_SETTING_KEY)
        if setting and setting.value:
            try:
                raw = json.loads(setting.value)
            except json.JSONDecodeError:
                raw = {}
            if isinstance(raw, dict):
                for key, value in raw.items():
                    if isinstance(key, str) and isinstance(value, str):
                        aliases[key.strip().upper()] = value.strip().upper()

    _quote_alias_cache[_QUOTE_ALIAS_CACHE_KEY] = aliases
    return aliases


def _search_symbol_for_isin(isin: str) -> str | None:
    url = "https://query2.finance.yahoo.com/v1/finance/search"
    params = {"q": isin, "quotesCount": 1, "newsCount": 0}
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(url, params=params)
            resp.raise_for_status()
            payload = resp.json()
    except httpx.HTTPError:
        return None

    quotes = payload.get("quotes") or []
    for quote in quotes:
        symbol = quote.get("symbol")
        if isinstance(symbol, str) and symbol.strip():
            return symbol.strip().upper()
    return None


def clear_quote_alias_cache() -> None:
    _quote_alias_cache.clear()


_EURONEXT_COMBINED_PATTERN = re.compile(
    r"^(?P<symbol>[A-Z0-9]+)[-_/](?P<isin>[A-Z]{2}[A-Z0-9]{9}[0-9])(?:[-_/](?P<mic>X[A-Z0-9]{3}|[A-Z]{2}))?$"
)
_EURONEXT_ISIN_MARKET_PATTERN = re.compile(
    r"^(?P<isin>[A-Z]{2}[A-Z0-9]{9}[0-9])[-_/](?P<mic>X[A-Z0-9]{3}|[A-Z]{2})$"
)
_EURONEXT_ISSUE_PATTERN = re.compile(
    r"^(?P<symbol>[A-Z0-9]+)[-_/](?P<isin>[A-Z]{2}[A-Z0-9]{9}[0-9])[-_/](?P<mic>X[A-Z0-9]{3})$"
)


def resolve_quote_symbol(symbol: str, type_portefeuille: str | None) -> str:
    if not symbol:
        return ""

    normalized_input = symbol.strip().upper()
    if not normalized_input:
        return ""

    normalized = normalized_input
    match = _EURONEXT_COMBINED_PATTERN.match(normalized)
    if match:
        normalized = match.group("isin")
    else:
        market_match = _EURONEXT_ISIN_MARKET_PATTERN.match(normalized)
        if market_match:
            normalized = market_match.group("isin")

    if (type_portefeuille or "").upper() == "CRYPTO":
        return normalized

    aliases = _load_quote_aliases()
    alias = aliases.get(normalized_input)
    if alias:
        return alias

    if normalized != normalized_input:
        alias = aliases.get(normalized)
        if alias:
            return alias

    if not _ISIN_REGEX.match(normalized):
        symbol_mic = _extract_symbol_mic(normalized_input)
        if not symbol_mic and normalized != normalized_input:
            symbol_mic = _extract_symbol_mic(normalized)

        if symbol_mic:
            base_symbol, mic = symbol_mic
            try:
                isin_value, resolved_mic = euronext.search_instrument_by_symbol(
                    base_symbol, mic
                )
            except euronext.EuronextAPIError:
                if mic:
                    try:
                        isin_value, resolved_mic = euronext.search_instrument_by_symbol(
                            base_symbol, None
                        )
                    except euronext.EuronextAPIError:
                        return normalized_input
                    else:
                        alias_value = f"{base_symbol}-{isin_value}-{resolved_mic}"
                        updated_aliases = dict(aliases)
                        updated_aliases[normalized_input] = alias_value
                        updated_aliases[isin_value] = alias_value
                        _quote_alias_cache[_QUOTE_ALIAS_CACHE_KEY] = updated_aliases
                        return alias_value
                return normalized_input
            else:
                alias_value = f"{base_symbol}-{isin_value}-{resolved_mic}"
                updated_aliases = dict(aliases)
                updated_aliases[normalized_input] = alias_value
                updated_aliases[isin_value] = alias_value
                _quote_alias_cache[_QUOTE_ALIAS_CACHE_KEY] = updated_aliases
                return alias_value
        return normalized_input

    alias = aliases.get(normalized)
    if alias:
        return alias

    fetched = _search_symbol_for_isin(normalized)
    if fetched:
        updated_aliases = dict(aliases)
        updated_aliases[normalized] = fetched
        _quote_alias_cache[_QUOTE_ALIAS_CACHE_KEY] = updated_aliases
        return fetched

    try:
        symbol_value, mic_value = euronext.search_instrument_by_isin(normalized)
    except euronext.EuronextAPIError:
        try:
            symbol_value, mic_value = euronext.lookup_instrument_by_isin(normalized)
        except euronext.EuronextAPIError:
            return normalized
    alias_value = f"{symbol_value}-{normalized}-{mic_value}"
    updated_aliases = dict(aliases)
    updated_aliases[normalized] = alias_value
    updated_aliases[normalized_input] = alias_value
    _quote_alias_cache[_QUOTE_ALIAS_CACHE_KEY] = updated_aliases
    return alias_value


def _normalize_mic(value: str | None) -> str | None:
    if not value:
        return None
    upper = value.strip().upper()
    if upper in _EURONEXT_MICS:
        return upper
    return _EURONEXT_SUFFIX_TO_MIC.get(upper)


def _normalize_issue(symbol: str, isin: str, mic: str) -> str:
    return f"{symbol.strip().upper()}-{isin.strip().upper()}-{mic.strip().upper()}"


def _derive_equity_fetch_symbol(resolved_symbol: str) -> str:
    normalized = (resolved_symbol or "").strip().upper()
    if not normalized:
        return normalized

    if _ISIN_REGEX.match(normalized):
        fetched = _search_symbol_for_isin(normalized)
        if fetched:
            return fetched
        return normalized

    issue_match = _EURONEXT_ISSUE_PATTERN.match(normalized)
    if issue_match:
        symbol = issue_match.group("symbol")
        mic = _normalize_mic(issue_match.group("mic"))
        if symbol and mic:
            suffix = _EURONEXT_MIC_TO_SUFFIX.get(mic)
            if suffix:
                return f"{symbol}.{suffix}"

    return normalized


def _extract_symbol_mic(candidate: str) -> Tuple[str, str] | None:
    for sep in ("-", ".", ":", "@", "/"):
        if sep in candidate:
            base, suffix = candidate.rsplit(sep, 1)
            base = base.strip().upper()
            mic = _normalize_mic(suffix)
            if base and mic:
                return base, mic
    return None


def _iter_euronext_candidates(original: str, resolved: str) -> Tuple[str, ...]:
    issues: list[str] = []
    seen_issues: set[str] = set()
    isins: list[str] = []
    seen_isins: set[str] = set()
    symbol_mics: list[Tuple[str, str]] = []
    seen_symbol_mics: set[Tuple[str, str]] = set()

    try:
        aliases = _quote_alias_cache[_QUOTE_ALIAS_CACHE_KEY]
    except KeyError:
        try:
            aliases = _load_quote_aliases()
        except Exception:
            aliases = {}

    raw_candidates: list[str] = []
    raw_seen: set[str] = set()

    def append_candidate(value: str | None) -> None:
        if not value:
            return
        normalized_value = value.strip()
        if not normalized_value:
            return
        upper_value = normalized_value.upper()
        if upper_value not in raw_seen:
            raw_seen.add(upper_value)
            raw_candidates.append(normalized_value)
        alias_value = aliases.get(normalized_value.upper())
        if alias_value and alias_value.upper() not in raw_seen:
            raw_seen.add(alias_value.upper())
            raw_candidates.append(alias_value)

    append_candidate(original)
    append_candidate(resolved)

    def add_issue(symbol: str, isin: str, mic: str) -> None:
        issue = _normalize_issue(symbol, isin, mic)
        if issue not in seen_issues:
            seen_issues.add(issue)
            issues.append(issue)

    def add_isin(value: str) -> None:
        upper = value.strip().upper()
        if upper and _ISIN_REGEX.match(upper) and upper not in seen_isins:
            seen_isins.add(upper)
            isins.append(upper)

    def add_symbol_mic(symbol: str, mic: str) -> None:
        key = (symbol.strip().upper(), mic.strip().upper())
        if key[0] and key[1] and key not in seen_symbol_mics:
            seen_symbol_mics.add(key)
            symbol_mics.append(key)

    for raw_candidate in raw_candidates:
        if not raw_candidate:
            continue
        normalized = raw_candidate.strip().upper()
        if not normalized:
            continue

        issue_match = _EURONEXT_ISSUE_PATTERN.match(normalized)
        if issue_match:
            add_issue(
                issue_match.group("symbol"),
                issue_match.group("isin"),
                issue_match.group("mic"),
            )
            continue

        combined_match = _EURONEXT_COMBINED_PATTERN.match(normalized)
        if combined_match:
            add_isin(combined_match.group("isin"))
            mic_value = combined_match.group("mic")
            if mic_value:
                mic = _normalize_mic(mic_value)
                if mic:
                    add_issue(combined_match.group("symbol"), combined_match.group("isin"), mic)
                    continue
            symbol = combined_match.group("symbol")
            if symbol:
                symbol_mic = _extract_symbol_mic(symbol)
                if symbol_mic:
                    add_symbol_mic(*symbol_mic)
            continue

        market_match = _EURONEXT_ISIN_MARKET_PATTERN.match(normalized)
        if market_match:
            mic = _normalize_mic(market_match.group("mic"))
            if mic:
                add_isin(market_match.group("isin"))
                for symbol, existing_mic in symbol_mics:
                    if existing_mic == mic:
                        add_issue(symbol, market_match.group("isin"), mic)
                continue

        symbol_mic = _extract_symbol_mic(normalized)
        if symbol_mic:
            add_symbol_mic(*symbol_mic)
            continue

        add_isin(normalized)

    for symbol, mic in symbol_mics:
        for isin in isins:
            add_issue(symbol, isin, mic)

    return tuple(issues)


def get_market_price(symbol: str, type_portefeuille: str | None) -> float:
    resolved_symbol = resolve_quote_symbol(symbol, type_portefeuille)
    cache_key = (resolved_symbol.upper(), (type_portefeuille or "").upper())

    normalized_type = (type_portefeuille or "").upper()
    if normalized_type != "CRYPTO":
        for candidate in _iter_euronext_candidates(symbol, resolved_symbol):
            meta = {
                "symbol": symbol,
                "resolved_symbol": resolved_symbol,
                "source": "euronext",
                "candidate": candidate,
            }
            _record_portfolio_log(
                "INFO",
                f"Fetching market price for {symbol} via Euronext candidate {candidate}",
                meta,
            )
            try:
                price = euronext.fetch_price(candidate)
            except euronext.EuronextAPIError as exc:
                _record_portfolio_log(
                    "WARNING",
                    f"Euronext price fetch failed for {symbol} candidate {candidate}: {exc}",
                    meta,
                )
                continue
            else:
                success_meta = {**meta, "price": price}
                _record_portfolio_log(
                    "INFO",
                    f"Euronext price fetch succeeded for {symbol} candidate {candidate} at price {price}",
                    success_meta,
                )
                _price_cache[cache_key] = price
                return price

    fetcher = _fetch_equity_price
    fetch_symbol = resolved_symbol
    adjusted_fetch_symbol = None
    derived_fetch_symbol = (fetch_symbol or "").strip().upper()
    if normalized_type == "CRYPTO":
        fetcher = _fetch_crypto_price
    else:
        fetch_symbol = _derive_equity_fetch_symbol(resolved_symbol)

        normalized_resolved = (resolved_symbol or "").strip().upper()
        derived_fetch_symbol = (fetch_symbol or "").strip().upper()

        needs_adjustment = False
        if _ISIN_REGEX.match(normalized_resolved):
            needs_adjustment = _ISIN_REGEX.match(derived_fetch_symbol) is not None
        else:
            if _EURONEXT_ISSUE_PATTERN.match(normalized_resolved):
                needs_adjustment = derived_fetch_symbol == normalized_resolved
            elif _EURONEXT_COMBINED_PATTERN.match(normalized_resolved):
                needs_adjustment = derived_fetch_symbol == normalized_resolved

        if needs_adjustment:
            adjusted_fetch_symbol = None
            if _ISIN_REGEX.match(normalized_resolved):
                adjusted_fetch_symbol = _search_symbol_for_isin(normalized_resolved)
            else:
                issue_match = _EURONEXT_ISSUE_PATTERN.match(normalized_resolved)
                if not issue_match:
                    combined_match = _EURONEXT_COMBINED_PATTERN.match(normalized_resolved)
                    if combined_match:
                        symbol = combined_match.group("symbol")
                        isin_value = combined_match.group("isin")
                        mic_value = combined_match.group("mic")
                        mic = _normalize_mic(mic_value) if mic_value else None
                        if symbol and mic:
                            suffix = _EURONEXT_MIC_TO_SUFFIX.get(mic)
                            if suffix:
                                adjusted_fetch_symbol = f"{symbol}.{suffix}"
                        if not adjusted_fetch_symbol and isin_value and _ISIN_REGEX.match(isin_value):
                            adjusted_fetch_symbol = _search_symbol_for_isin(isin_value)
                else:
                    symbol = issue_match.group("symbol")
                    mic_value = issue_match.group("mic")
                    mic = _normalize_mic(mic_value)
                    if symbol and mic:
                        suffix = _EURONEXT_MIC_TO_SUFFIX.get(mic)
                        if suffix:
                            adjusted_fetch_symbol = f"{symbol}.{suffix}"
                    if not adjusted_fetch_symbol:
                        isin_value = issue_match.group("isin")
                        if isin_value and _ISIN_REGEX.match(isin_value):
                            adjusted_fetch_symbol = _search_symbol_for_isin(isin_value)

            if adjusted_fetch_symbol:
                fetch_symbol = adjusted_fetch_symbol

        adjustment_meta: Dict[str, object] = {}
        if adjusted_fetch_symbol and adjusted_fetch_symbol != derived_fetch_symbol:
            adjustment_meta = {
                "adjusted_fetch_symbol": adjusted_fetch_symbol,
                "initial_fetch_symbol": derived_fetch_symbol,
            }

        _record_portfolio_log(
            "WARNING",
            f"Falling back to secondary price source for {symbol}",
            {
                "symbol": symbol,
                "resolved_symbol": resolved_symbol,
                "source": fetcher.__name__,
                "type_portefeuille": normalized_type,
                "fetch_symbol": fetch_symbol,
                **adjustment_meta,
            },
        )

    attempt_meta = {
        "symbol": symbol,
        "resolved_symbol": resolved_symbol,
        "source": fetcher.__name__,
        "type_portefeuille": normalized_type,
        "fetch_symbol": fetch_symbol,
    }
    if adjusted_fetch_symbol and adjusted_fetch_symbol != derived_fetch_symbol:
        attempt_meta["adjusted_fetch_symbol"] = adjusted_fetch_symbol
        attempt_meta["initial_fetch_symbol"] = derived_fetch_symbol
    _record_portfolio_log(
        "INFO",
        f"Fetching market price for {symbol} via {fetcher.__name__}",
        attempt_meta,
    )

    try:
        price = fetcher(fetch_symbol)
    except MarketPriceUnavailable:
        _record_portfolio_log(
            "ERROR",
            f"Market price unavailable for {symbol} via {fetcher.__name__}",
            attempt_meta,
        )
        if cache_key in _price_cache:
            return _price_cache[cache_key]
        raise
    else:
        success_meta = {**attempt_meta, "price": price}
        _record_portfolio_log(
            "INFO",
            f"Price fetched for {symbol} via {fetcher.__name__} at price {price}",
            success_meta,
        )
        _price_cache[cache_key] = price
        return price


@cached(cache=_cache, key=lambda *_args, **_kwargs: "portfolio_holdings")
def compute_holdings(db: Session) -> Tuple[List[HoldingView], Dict[str, float]]:
    txs: List[Transaction] = db.query(Transaction).order_by(Transaction.trade_date.asc(), Transaction.id.asc()).all()
    fifo = FIFOPortfolio()
    portfolio_types: Dict[PortfolioKey, str] = {}
    symbol_labels: Dict[PortfolioKey, str] = {}
    account_labels: Dict[PortfolioKey, str | None] = {}
    realized_total = 0.0

    for tx in txs:
        raw_symbol = (tx.symbol_or_isin or tx.asset or "").strip()
        symbol = _normalize_symbol(raw_symbol or tx.asset)
        portfolio_type = _normalize_portfolio_type(tx.portfolio_type)
        key = _make_portfolio_key(tx.portfolio_type, raw_symbol or tx.asset, tx.account_id)
        total_eur = tx.total_eur
        portfolio_types[key] = portfolio_type
        if key not in symbol_labels or not symbol_labels[key]:
            symbol_labels[key] = symbol
        current_account = account_labels.get(key)
        if current_account is None and tx.account_id is not None:
            account_labels[key] = tx.account_id
        elif key not in account_labels:
            account_labels[key] = tx.account_id

        operation = (tx.operation or "").upper()

        if operation == "BUY":
            fifo.buy(key, tx.quantity, total_eur + tx.fee_eur)
        elif operation == "SELL":
            asset_label = (tx.asset or "").strip()
            symbol_label = (tx.symbol_or_isin or "").strip()

            if _contains_fiat_code(asset_label) or _contains_fiat_code(symbol_label):
                realized_total += total_eur - tx.fee_eur
                continue
            realized_total += fifo.sell(key, tx.quantity, total_eur, fee_eur=tx.fee_eur)
        elif operation == "DIVIDEND":
            fifo.dividend(key, total_eur - tx.fee_eur)
            realized_total += total_eur - tx.fee_eur
        else:
            # treat cash movements as realized adjustments but no holdings impact
            realized_total += total_eur
            continue

    as_of = utc_now()
    holdings: List[HoldingView] = []
    for key in fifo.as_dict():
        qty, cost = fifo.current_position(key)
        if qty <= 1e-12:
            continue
        try:
            market_price = get_market_price(symbol_labels.get(key, key[1]), portfolio_types.get(key))
        except MarketPriceUnavailable:
            market_price = cost / qty if qty else 0.0
        market_value = market_price * qty
        invested = cost
        pl_latent = market_value - invested
        pl_pct = (pl_latent / invested * 100.0) if invested else 0.0
        type_portefeuille = portfolio_types.get(key, "PEA")
        symbol_display = symbol_labels.get(key, key[1])
        identifier = _build_identifier_from_key(key)
        holdings.append(
            HoldingView(
                identifier=identifier,
                asset=symbol_display,
                symbol_or_isin=symbol_display,
                quantity=qty,
                pru_eur=invested / qty,
                invested_eur=invested,
                market_price_eur=market_price,
                market_value_eur=market_value,
                pl_eur=pl_latent,
                pl_pct=pl_pct,
                type_portefeuille=type_portefeuille,
                as_of=as_of,
                account_id=account_labels.get(key),
            )
        )

    totals = {
        "total_value": sum(h.market_value_eur for h in holdings),
        "total_invested": sum(h.invested_eur for h in holdings),
        "realized_pnl": realized_total,
        "latent_pnl": sum(h.pl_eur for h in holdings),
    }

    return holdings, totals


def compute_holding_detail(db: Session, identifier: str) -> HoldingDetailView:
    if not identifier:
        raise HoldingNotFound("Missing holding identifier")

    normalized = identifier.strip().upper()
    symbol_hint, type_hint, account_hint = _parse_identifier(identifier)
    holdings, _ = compute_holdings(db)
    holding: HoldingView | None = None

    for candidate in holdings:
        if candidate.identifier.upper() == normalized:
            holding = candidate
            break

    if holding is None:
        for candidate in holdings:
            candidate_symbol = _normalize_symbol(candidate.symbol_or_isin or candidate.asset)
            candidate_type = _normalize_portfolio_type(candidate.type_portefeuille)
            candidate_account = _normalize_account_id(candidate.account_id)
            if symbol_hint and candidate_symbol != symbol_hint:
                continue
            if type_hint and candidate_type != type_hint:
                continue
            if account_hint and candidate_account != account_hint:
                continue
            holding = candidate
            break

    if holding is None:
        for candidate in holdings:
            if (candidate.symbol_or_isin or "").upper() == normalized or candidate.asset.upper() == normalized:
                holding = candidate
                break

    if holding is None:
        raise HoldingNotFound(f"Holding '{identifier}' not found")

    symbol_normalized = _normalize_symbol(holding.symbol_or_isin or holding.asset)
    type_normalized = _normalize_portfolio_type(holding.type_portefeuille)
    account_normalized = _normalize_account_id(holding.account_id)

    tx_query = (
        db.query(Transaction)
        .filter(
            or_(
                func.upper(Transaction.symbol_or_isin) == symbol_normalized,
                func.upper(Transaction.asset) == symbol_normalized,
            )
        )
        .filter(func.upper(Transaction.portfolio_type) == type_normalized)
    )
    if account_normalized:
        tx_query = tx_query.filter(func.upper(Transaction.account_id) == account_normalized)
    tx_rows = tx_query.order_by(Transaction.trade_date.asc(), Transaction.id.asc()).all()

    fifo = FIFOPortfolio()
    fifo_key = _make_portfolio_key(
        holding.type_portefeuille, holding.symbol_or_isin or holding.asset, holding.account_id
    )
    history: List[HoldingHistoryPointView] = []
    last_price = None
    for tx in tx_rows:
        operation = (tx.operation or "").upper()
        if tx.unit_price_eur is not None:
            last_price = tx.unit_price_eur
        if operation == "BUY":
            fifo.buy(fifo_key, tx.quantity, tx.total_eur + tx.fee_eur)
        elif operation == "SELL":
            fifo.sell(fifo_key, tx.quantity, tx.total_eur, fee_eur=tx.fee_eur)
        elif operation == "DIVIDEND":
            fifo.dividend(fifo_key, tx.total_eur - tx.fee_eur)
        else:
            fifo.dividend(fifo_key, tx.total_eur)

        qty, cost_basis = fifo.current_position(fifo_key)
        if last_price is None:
            last_price = holding.market_price_eur
        market_price = last_price if last_price is not None else holding.market_price_eur
        market_value = market_price * qty
        pl_eur = market_value - cost_basis
        pl_pct = (pl_eur / cost_basis * 100.0) if cost_basis else 0.0
        history.append(
            HoldingHistoryPointView(
                ts=tx.trade_date,
                quantity=qty,
                invested_eur=cost_basis,
                market_price_eur=market_price,
                market_value_eur=market_value,
                pl_eur=pl_eur,
                pl_pct=pl_pct,
                operation=operation or "UNKNOWN",
            )
        )

    state = fifo.as_dict().get(fifo_key)
    realized = state.realized_pnl if state else 0.0
    dividends = sum(
        (tx.total_eur - tx.fee_eur)
        for tx in tx_rows
        if (tx.operation or "").upper() == "DIVIDEND"
    )

    return HoldingDetailView(
        identifier=holding.identifier,
        asset=holding.asset,
        symbol_or_isin=holding.symbol_or_isin,
        quantity=holding.quantity,
        pru_eur=holding.pru_eur,
        invested_eur=holding.invested_eur,
        market_price_eur=holding.market_price_eur,
        market_value_eur=holding.market_value_eur,
        pl_eur=holding.pl_eur,
        pl_pct=holding.pl_pct,
        type_portefeuille=holding.type_portefeuille,
        as_of=holding.as_of,
        account_id=holding.account_id,
        history=history,
        realized_pnl_eur=realized,
        dividends_eur=dividends,
        history_available=bool(history),
    )

