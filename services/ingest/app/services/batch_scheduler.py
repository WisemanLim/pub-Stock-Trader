"""일별 배치 스케줄러 — 장 마감 후 KRX OPEN API 자동 수집."""
from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.core.config import settings
from app.services.krx_openapi import KrxOpenApiService
from app.services.ohlcv_store import upsert_investor_flow, upsert_ohlcv

logger = logging.getLogger(__name__)

# 모듈 수준 단일 인스턴스
_scheduler: BackgroundScheduler | None = None
_last_run: dict[str, Any] = {"status": "never", "at": None, "saved": 0, "errors": []}


def _run_daily_batch() -> None:
    """장 마감 후 전일 OHLCV + 투자자 수급 수집."""
    global _last_run
    tickers: list[str] = settings.scheduler_tickers
    if not tickers:
        logger.info("batch_scheduler: 수집 종목 없음 (SCHEDULER_TICKERS 미설정)")
        return

    svc = KrxOpenApiService(
        api_key=settings.krx_open_api_key,
        rate_limit=settings.krx_api_rate_limit,
    )
    if not svc.configured:
        logger.warning("batch_scheduler: KRX_OPEN_API_KEY 미설정 — 건너뜀")
        _last_run = {"status": "skipped", "at": _now(), "saved": 0,
                     "errors": ["KRX_OPEN_API_KEY not configured"]}
        return

    today = date.today()
    yesterday = today - timedelta(days=1)
    from_date = yesterday.strftime("%Y%m%d")
    to_date = today.strftime("%Y%m%d")

    total_saved = 0
    errors: list[str] = []

    for ticker in tickers:
        try:
            # OHLCV
            ohlcv = svc.get_daily_ohlcv(ticker, from_date, to_date)
            saved = upsert_ohlcv(ticker, ohlcv)
            total_saved += saved
            # 투자자 수급
            flow = svc.get_investor_flow(ticker, from_date, to_date)
            saved_f = upsert_investor_flow(ticker, flow)
            total_saved += saved_f
            logger.info(f"batch_scheduler: {ticker} ohlcv={len(ohlcv)} flow={len(flow)} saved={saved+saved_f}")
        except Exception as exc:
            msg = f"{ticker}: {exc}"
            logger.error(f"batch_scheduler error — {msg}")
            errors.append(msg)

    _last_run = {
        "status": "error" if errors else "ok",
        "at": _now(),
        "saved": total_saved,
        "errors": errors,
    }
    logger.info(f"batch_scheduler: 완료 saved={total_saved} errors={len(errors)}")


def _now() -> str:
    from datetime import datetime
    return datetime.utcnow().isoformat() + "Z"


def start() -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        return
    _scheduler = BackgroundScheduler(timezone="Asia/Seoul")
    # 평일(월~금) 15:40 KST 실행
    h, m = settings.scheduler_hour, settings.scheduler_minute
    _scheduler.add_job(
        _run_daily_batch,
        trigger=CronTrigger(day_of_week="mon-fri", hour=h, minute=m, timezone="Asia/Seoul"),
        id="daily_ohlcv_batch",
        replace_existing=True,
    )
    _scheduler.start()
    logger.info(f"batch_scheduler: 시작 ({h:02d}:{m:02d} KST 평일)")


def stop() -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("batch_scheduler: 중지")


def run_now() -> dict[str, Any]:
    """수동 즉시 실행 (API 트리거용)."""
    _run_daily_batch()
    return _last_run


def status() -> dict[str, Any]:
    running = bool(_scheduler and _scheduler.running)
    job = _scheduler.get_job("daily_ohlcv_batch") if running else None
    return {
        "running": running,
        "tickers": settings.scheduler_tickers,
        "schedule": f"{settings.scheduler_hour:02d}:{settings.scheduler_minute:02d} KST (평일)",
        "krx_configured": bool(settings.krx_open_api_key),
        "last_run": _last_run,
        "next_run": job.next_run_time.isoformat() if job and job.next_run_time else None,
    }
