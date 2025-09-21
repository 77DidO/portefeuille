from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, AsyncGenerator, Dict

import httpx
from loguru import logger

from app.core.config import settings
from app.core.security import sign_external_ref
from app.models.system_logs import SystemLog
from app.utils.time import utc_now

BINANCE_REST = "https://api.binance.com"
BINANCE_WS = "wss://stream.binance.com:9443/ws"


@dataclass
class MiniTicker:
    symbol: str
    price: float
    event_time: int


async def fetch_price(symbol: str) -> float:
    async with httpx.AsyncClient(base_url=BINANCE_REST, timeout=10.0) as client:
        resp = await client.get("/api/v3/ticker/price", params={"symbol": symbol.upper()})
        resp.raise_for_status()
        data = resp.json()
        return float(data["price"])


async def mini_ticker_stream(symbols: list[str]) -> AsyncGenerator[MiniTicker, None]:
    import json
    import websockets

    streams = "/".join(f"{symbol.lower()}@miniTicker" for symbol in symbols)
    url = f"{BINANCE_WS}/{streams}"
    async with websockets.connect(url, ping_interval=20, ping_timeout=20) as ws:
        async for msg in ws:
            payload = json.loads(msg)
            yield MiniTicker(symbol=payload["s"], price=float(payload["c"]), event_time=payload["E"])


def record_log(db, level: str, component: str, message: str, meta: Dict[str, Any] | None = None) -> None:
    log = SystemLog(ts=utc_now(), level=level, component=component, message=message, meta_json=(meta and str(meta)) or None)
    db.add(log)
    db.commit()


async def backfill(db) -> None:
    record_log(db, "INFO", "binance", "Backfill démarré")
    await asyncio.sleep(0.1)
    record_log(db, "INFO", "binance", "Backfill terminé")
