from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import re
from typing import Dict, Iterable, List, Tuple

from cachetools import TTLCache, cached
from sqlalchemy.orm import Session

from app.models.transactions import Transaction
from app.services.fifo import FIFOPortfolio
from app.utils.time import utc_now


@dataclass
class HoldingView:
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


_cache = TTLCache(maxsize=1, ttl=120)


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


def _market_price_placeholder(symbol: str) -> float:
    # Placeholder deterministic price for demo/seeding. Real impl should fetch Yahoo/Binance.
    base_prices = {
        "BTC": 65000.0,
        "ETH": 3500.0,
    }
    return base_prices.get(symbol.upper(), 100.0)


@cached(_cache)
def compute_holdings(db: Session) -> Tuple[List[HoldingView], Dict[str, float]]:
    txs: List[Transaction] = db.query(Transaction).order_by(Transaction.ts.asc(), Transaction.id.asc()).all()
    fifo = FIFOPortfolio()
    holdings_map: Dict[str, HoldingView] = {}
    portfolio_types: Dict[str, str] = {}
    realized_total = 0.0

    for tx in txs:
        symbol = (tx.symbol_or_isin or tx.asset or "").upper()
        total_eur = tx.total_eur
        if symbol and tx.type_portefeuille:
            portfolio_types[symbol] = tx.type_portefeuille.upper()

        if tx.operation.upper() == "BUY":
            fifo.buy(symbol, tx.quantity, total_eur + tx.fee_eur)
        elif tx.operation.upper() == "SELL":
            asset_label = (tx.asset or "").strip()
            symbol_label = (tx.symbol_or_isin or "").strip()

            if _contains_fiat_code(asset_label) or _contains_fiat_code(symbol_label):
                realized_total += total_eur - tx.fee_eur
                continue
            realized_total += fifo.sell(symbol, tx.quantity, total_eur, fee_eur=tx.fee_eur)
        elif tx.operation.upper() == "DIVIDEND":
            fifo.dividend(symbol, total_eur - tx.fee_eur)
            realized_total += total_eur - tx.fee_eur
        else:
            # treat cash movements as realized adjustments but no holdings impact
            realized_total += total_eur
            continue

    as_of = utc_now()
    holdings: List[HoldingView] = []
    for symbol, state in fifo.as_dict().items():
        qty, cost = fifo.current_position(symbol)
        if qty <= 1e-12:
            continue
        market_price = _market_price_placeholder(symbol)
        market_value = market_price * qty
        invested = cost
        pl_latent = market_value - invested
        pl_pct = (pl_latent / invested * 100.0) if invested else 0.0
        type_portefeuille = portfolio_types.get(symbol, "PEA")
        holdings.append(
            HoldingView(
                asset=symbol,
                symbol_or_isin=symbol,
                quantity=qty,
                pru_eur=invested / qty,
                invested_eur=invested,
                market_price_eur=market_price,
                market_value_eur=market_value,
                pl_eur=pl_latent,
                pl_pct=pl_pct,
                type_portefeuille=type_portefeuille,
                as_of=as_of,
            )
        )

    totals = {
        "total_value": sum(h.market_value_eur for h in holdings),
        "total_invested": sum(h.invested_eur for h in holdings),
        "realized_pnl": realized_total,
        "latent_pnl": sum(h.pl_eur for h in holdings),
    }

    return holdings, totals
