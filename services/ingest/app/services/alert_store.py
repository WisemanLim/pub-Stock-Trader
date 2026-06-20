"""B-1: 시장경보 DB 적재 — upsert (ticker+date+level 중복 무시)."""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.exc import IntegrityError

from app.db import MarketAlertDaily, get_session
from app.services.ohlcv_store import _parse_date

logger = logging.getLogger(__name__)


def upsert_alerts(rows: list[dict[str, Any]]) -> int:
    """시장경보 행 목록을 DB에 적재. 이미 있는 (ticker, date, level)은 무시.
    Returns 저장된 행 수."""
    if not rows:
        return 0
    saved = 0
    with get_session() as session:
        for r in rows:
            d = _parse_date(str(r.get("date", "")))
            ticker = str(r.get("ticker", "")).strip()
            level = str(r.get("level", "")).strip()
            if not ticker or not level or d is None:
                continue
            row = MarketAlertDaily(
                ticker=ticker,
                date=d,
                level=level,
                name=str(r.get("name", "")),
                source="krx_kind",
            )
            try:
                session.add(row)
                session.flush()
                saved += 1
            except IntegrityError:
                session.rollback()
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
    return saved


def get_active_alerts(ticker: str | None = None) -> list[dict[str, Any]]:
    """DB에서 시장경보 조회. ticker 미지정 시 전체."""
    from sqlalchemy import select, desc

    with get_session() as session:
        stmt = select(MarketAlertDaily).order_by(desc(MarketAlertDaily.date))
        if ticker:
            stmt = stmt.where(MarketAlertDaily.ticker == ticker)
        rows = session.execute(stmt).scalars().all()
        return [
            {
                "ticker": r.ticker,
                "name": r.name,
                "level": r.level,
                "date": r.date.isoformat() if r.date else None,
            }
            for r in rows
        ]
