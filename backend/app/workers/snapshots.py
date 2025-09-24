from __future__ import annotations

from dataclasses import replace

from sqlalchemy.orm import Session

from app.models.holdings import Holding
from app.models.snapshots import Snapshot
from app.services.portfolio import compute_holdings, _normalize_portfolio_type
from app.services.system_logs import record_log
from app.utils.time import utc_now


_SNAPSHOT_PORTFOLIO_TYPE_ALIASES = {
    "PEA-PME": "PEA",
    "PEA PME": "PEA",
    "PEAPME": "PEA",
    "PEAJEUNE": "PEA",
    "PEA JEUNE": "PEA",
    "PEA-JEUNE": "PEA",
    "CRYPTO BINANCE": "CRYPTO",
    "CRYPTO-BINANCE": "CRYPTO",
}


def _normalize_snapshot_portfolio_type(value: str | None) -> str:
    normalized = _normalize_portfolio_type(value)

    alias = _SNAPSHOT_PORTFOLIO_TYPE_ALIASES.get(normalized)
    if alias:
        return alias

    if normalized != "PEA" and normalized.startswith("PEA"):
        return "PEA"
    if normalized != "CRYPTO" and normalized.startswith("CRYPTO"):
        return "CRYPTO"
    return normalized


def run_snapshot(db: Session) -> Snapshot:
    record_log(db, "INFO", "snapshots", "Snapshot recomputation started")
    compute_holdings.cache_clear()
    holdings, totals = compute_holdings(db)

    normalized_holdings = []
    value_pea = 0.0
    value_crypto = 0.0
    value_other = 0.0

    for holding in holdings:
        normalized_type = _normalize_snapshot_portfolio_type(holding.type_portefeuille)
        normalized_holdings.append(replace(holding, type_portefeuille=normalized_type))
        if normalized_type == "PEA":
            value_pea += holding.market_value_eur
        elif normalized_type == "CRYPTO":
            value_crypto += holding.market_value_eur
        else:
            value_other += holding.market_value_eur

    ts = utc_now()
    value_total = value_pea + value_crypto + value_other
    pnl_total = totals["realized_pnl"] + totals["latent_pnl"]

    snapshot = Snapshot(
        ts=ts,
        value_pea_eur=value_pea,
        value_crypto_eur=value_crypto,
        value_total_eur=value_total,
        pnl_total_eur=pnl_total,
    )
    db.add(snapshot)
    db.commit()
    db.refresh(snapshot)

    for holding in normalized_holdings:
        db.add(
            Holding(
                asset=holding.asset,
                symbol_or_isin=holding.symbol_or_isin,
                symbol=holding.symbol,
                isin=holding.isin,
                mic=holding.mic,
                quantity=holding.quantity,
                pru_eur=holding.pru_eur,
                invested_eur=holding.invested_eur,
                market_price_eur=holding.market_price_eur,
                market_value_eur=holding.market_value_eur,
                pl_eur=holding.pl_eur,
                pl_pct=holding.pl_pct,
                as_of=holding.as_of,
                portfolio_type=holding.type_portefeuille,
                account_id=holding.account_id,
            )
        )
    db.commit()
    record_log(
        db,
        "INFO",
        "snapshots",
        "Snapshot recomputation completed",
        meta={
            "snapshot": {
                "id": snapshot.id,
                "value_pea_eur": value_pea,
                "value_crypto_eur": value_crypto,
                "value_total_eur": value_total,
                "value_other_eur": value_other,
                "pnl_total_eur": pnl_total,
            }
        },
    )
    return snapshot
