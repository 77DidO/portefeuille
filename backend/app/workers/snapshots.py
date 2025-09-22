from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.models.holdings import Holding
from app.models.snapshots import Snapshot
from app.services.portfolio import compute_holdings
from app.utils.time import utc_now


def run_snapshot(db: Session) -> Snapshot:
    compute_holdings.cache_clear()
    holdings, totals = compute_holdings(db)
    ts = utc_now()
    value_crypto = sum(h.market_value_eur for h in holdings if h.type_portefeuille == "CRYPTO")
    value_pea = sum(h.market_value_eur for h in holdings if h.type_portefeuille != "CRYPTO")
    value_total = sum(h.market_value_eur for h in holdings)
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

    for holding in holdings:
        db.add(
            Holding(
                asset=holding.asset,
                symbol_or_isin=holding.symbol_or_isin,
                quantity=holding.quantity,
                pru_eur=holding.pru_eur,
                invested_eur=holding.invested_eur,
                market_price_eur=holding.market_price_eur,
                market_value_eur=holding.market_value_eur,
                pl_eur=holding.pl_eur,
                pl_pct=holding.pl_pct,
                as_of=holding.as_of,
                type_portefeuille=holding.type_portefeuille,
                account_id=holding.account_id,
            )
        )
    db.commit()
    return snapshot
