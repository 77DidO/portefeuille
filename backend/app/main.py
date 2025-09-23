from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from datetime import time

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app.api import configuration, export, health, journal, portfolio, snapshots, transactions
from app.core.config import settings
from app.core.logging import setup_logging
from app.db import base  # noqa: F401
from app.db.migration import run_migrations
from app.db.session import SessionLocal
from app.models.transactions import Transaction
from app.utils.time import PARIS_TZ
from app.workers.snapshots import run_snapshot

setup_logging()

scheduler = AsyncIOScheduler(timezone=PARIS_TZ)
app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event() -> None:
    run_migrations()
    if not scheduler.running:
        scheduler.start()
        trigger = CronTrigger(hour=settings.snapshot_hour, minute=settings.snapshot_minute, timezone=PARIS_TZ)
        scheduler.add_job(schedule_snapshot, trigger=trigger, id="daily_snapshot", replace_existing=True)
    seed_demo()


@app.on_event("shutdown")
async def shutdown_event() -> None:
    if scheduler.running:
        scheduler.shutdown()


async def schedule_snapshot():
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, _snapshot_job)


def _snapshot_job():
    db = SessionLocal()
    try:
        run_snapshot(db)
    finally:
        db.close()


@app.get("/")
def root():
    return {"app": settings.app_name}


def seed_demo() -> None:
    db = SessionLocal()
    try:
        if db.query(Transaction).count() == 0 and settings.demo_seed:
            from datetime import datetime, timezone

            from app.core.security import sign_transaction_uid

            sample = Transaction(
                source="binance",
                portfolio_type="CRYPTO",
                operation="BUY",
                asset="Bitcoin",
                symbol_or_isin="BTC",
                symbol="BTC",
                quantity=0.01,
                unit_price_eur=60000.0,
                fee_eur=1.0,
                fee_asset="EUR",
                fee_quantity=None,
                total_eur=600.0,
                trade_date=datetime(2024, 1, 10, 12, 0, tzinfo=timezone.utc),
                notes="Seed demo",
                transaction_uid=sign_transaction_uid({"sample": "tx1"}),
            )
            db.add(sample)
            db.commit()
    finally:
        db.close()


app.include_router(health.router)
app.include_router(portfolio.router)
app.include_router(transactions.router)
app.include_router(snapshots.router)
app.include_router(journal.router)
app.include_router(configuration.router)
app.include_router(export.router)
