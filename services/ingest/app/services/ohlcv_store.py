"""OHLCV / 투자자 수급 DB 적재 — upsert (date+ticker 중복 무시)."""
from __future__ import annotations

import logging
from datetime import date as _date
from typing import Any

from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import IntegrityError

from app.db import InvestorFlowDaily, OhlcvDaily, get_session

logger = logging.getLogger(__name__)


def _parse_date(d: str) -> _date | None:
    for fmt in ("%Y%m%d", "%Y-%m-%d"):
        try:
            from datetime import datetime

            return datetime.strptime(d, fmt).date()
        except ValueError:
            continue
    return None


def upsert_ohlcv(ticker: str, rows: list[dict[str, Any]]) -> int:
    """OHLCV 행 목록을 DB에 적재. 이미 있는 날짜는 무시(INSERT OR IGNORE).
    Returns 저장된 행 수."""
    if not rows:
        return 0
    saved = 0
    with get_session() as session:
        for r in rows:
            d = _parse_date(str(r.get("date", "")))
            if d is None:
                continue
            row = OhlcvDaily(
                ticker=ticker,
                date=d,
                open=r.get("open"),
                high=r.get("high"),
                low=r.get("low"),
                close=r.get("close"),
                volume=r.get("volume"),
                change_pct=r.get("change_pct"),
                source=str(r.get("source", "krx")),
            )
            try:
                session.add(row)
                session.flush()
                saved += 1
            except IntegrityError:
                session.rollback()  # 중복 키 → 무시
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
    return saved


def upsert_investor_flow(ticker: str, rows: list[dict[str, Any]]) -> int:
    """투자자 수급 행 목록을 DB에 적재."""
    if not rows:
        return 0
    saved = 0
    with get_session() as session:
        for r in rows:
            d = _parse_date(str(r.get("date", "")))
            if d is None:
                continue
            row = InvestorFlowDaily(
                ticker=ticker,
                date=d,
                institution_net=r.get("institution"),
                foreign_net=r.get("foreign"),
                individual_net=r.get("individual"),
                source=str(r.get("source", "krx")),
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


def latest_ohlcv_date(ticker: str) -> _date | None:
    """DB에서 해당 종목의 최신 날짜 반환."""
    with get_session() as session:
        from sqlalchemy import func, select

        stmt = select(func.max(OhlcvDaily.date)).where(OhlcvDaily.ticker == ticker)
        return session.execute(stmt).scalar()
