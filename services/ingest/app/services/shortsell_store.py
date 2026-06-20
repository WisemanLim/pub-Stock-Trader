"""B-3: 공매도 일별 통계 DB 적재 — upsert (ticker+date 중복 무시)."""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.exc import IntegrityError

from app.db import ShortSellingDaily, get_session
from app.services.ohlcv_store import _parse_date

logger = logging.getLogger(__name__)


def upsert_short_selling(ticker: str, rows: list[dict[str, Any]]) -> int:
    """공매도 통계 행 목록을 DB에 적재. 중복(ticker, date)은 무시.
    Returns 저장된 행 수."""
    if not rows:
        return 0
    saved = 0
    with get_session() as session:
        for r in rows:
            d = _parse_date(str(r.get("date", "")))
            if d is None:
                continue
            row = ShortSellingDaily(
                ticker=ticker,
                date=d,
                short_vol=_to_int(r.get("short_vol", 0)),
                short_val=_to_int(r.get("short_val", 0)),
                short_ratio=_to_float(r.get("short_ratio", 0.0)),
                source=str(r.get("source", "krx_openapi")),
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


def get_short_selling(ticker: str, limit: int = 60) -> list[dict[str, Any]]:
    """DB에서 공매도 통계 조회 (최신 순)."""
    from sqlalchemy import select, desc

    with get_session() as session:
        stmt = (
            select(ShortSellingDaily)
            .where(ShortSellingDaily.ticker == ticker)
            .order_by(desc(ShortSellingDaily.date))
            .limit(limit)
        )
        rows = session.execute(stmt).scalars().all()
        return [
            {
                "date": r.date.isoformat() if r.date else None,
                "short_vol": r.short_vol,
                "short_val": r.short_val,
                "short_ratio": r.short_ratio,
            }
            for r in rows
        ]


def _to_int(v: Any) -> int:
    try:
        return int(str(v).replace(",", "").strip())
    except (ValueError, TypeError):
        return 0


def _to_float(v: Any) -> float:
    try:
        return float(str(v).replace(",", "").strip())
    except (ValueError, TypeError):
        return 0.0
