from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import AsyncGenerator, Dict

import httpx

from app.core.config import settings
from app.core.security import sign_external_ref
from app.db.session import SessionLocal
from app.services.system_logs import record_log

BINANCE_REST = "https://api.binance.com"
BINANCE_WS = "wss://stream.binance.com:9443/ws"


logger = logging.getLogger(__name__)


@dataclass
class MiniTicker:
    symbol: str
    price: float
    event_time: int


def _record_binance_log(level: str, message: str, meta: Dict[str, object] | None = None) -> None:
    log_level = logging._nameToLevel.get(level.upper(), logging.INFO)
    logger.log(log_level, message)

    try:
        with SessionLocal() as db:
            record_log(db, level.upper(), "binance", message, meta=meta)
    except Exception as exc:  # pragma: no cover - logging should not interfere with pricing
        logger.warning(
            "Failed to record Binance system log: %s",
            exc,
            extra={"meta": meta},
        )


async def fetch_price(symbol: str) -> float:
    normalized = symbol.upper()
    params = {"symbol": normalized}
    request_meta = {"symbol": normalized, "url": f"{BINANCE_REST}/api/v3/ticker/price", "params": params}
    _record_binance_log(
        "INFO",
        f"Requesting Binance price for {normalized}",
        request_meta,
    )

    async with httpx.AsyncClient(base_url=BINANCE_REST, timeout=10.0) as client:
        try:
            resp = await client.get("/api/v3/ticker/price", params=params)
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPStatusError as exc:
            error_meta = {**request_meta, "status_code": exc.response.status_code}
            _record_binance_log(
                "WARNING",
                f"Binance HTTP error {exc.response.status_code} for {normalized}",
                error_meta,
            )
            raise
        except httpx.HTTPError as exc:
            _record_binance_log(
                "ERROR",
                f"Binance request failed for {normalized}: {exc}",
                request_meta,
            )
            raise

    try:
        price = float(data["price"])
    except (KeyError, TypeError, ValueError) as exc:
        _record_binance_log(
            "ERROR",
            f"Unexpected Binance payload for {normalized}: {exc}",
            {**request_meta, "payload": data},
        )
        raise

    _record_binance_log(
        "INFO",
        f"Binance price for {normalized} is {price}",
        {**request_meta, "price": price},
    )
    return price


async def mini_ticker_stream(symbols: list[str]) -> AsyncGenerator[MiniTicker, None]:
    import json
    import websockets

    streams = "/".join(f"{symbol.lower()}@miniTicker" for symbol in symbols)
    url = f"{BINANCE_WS}/{streams}"
    async with websockets.connect(url, ping_interval=20, ping_timeout=20) as ws:
        async for msg in ws:
            payload = json.loads(msg)
            yield MiniTicker(symbol=payload["s"], price=float(payload["c"]), event_time=payload["E"])

async def backfill(db) -> None:
    record_log(db, "INFO", "binance", "Backfill démarré")
    await asyncio.sleep(0.1)
    record_log(db, "INFO", "binance", "Backfill terminé")
