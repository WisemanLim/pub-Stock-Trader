"""D-1: ESG 점수 집계 — FDR 재무 프록시 기반 ESG 스코어링.

KRX OPEN API 무료 티어에서 별도 ESG 엔드포인트가 없으므로
FDR 재무·거래 데이터로 간이 ESG 프록시 점수(0~100)를 산출한다.

점수 구성:
  E(환경) 20점 — 거래량 대비 시가총액 비율 (규모·효율 프록시)
  S(사회)  30점 — 기관 투자자 비중 프록시 (기관 참여 = 사회적 검증)
  G(지배)  50점 — 주가 변동성 역수 (낮은 변동성 = 안정적 지배구조)
"""
import threading
import time
from datetime import datetime, timedelta, timezone

import FinanceDataReader as fdr
import pandas as pd

_CACHE: dict[str, dict] = {}
_LOCK = threading.Lock()
_CACHE_TTL = 3600 * 6  # 6시간


def _calc_esg(ticker: str) -> dict:
    try:
        end = datetime.now(timezone.utc)
        start = end - timedelta(days=60)
        df = fdr.DataReader(ticker, start.strftime("%Y-%m-%d"))
        if len(df) < 20:
            return _empty(ticker)

        df = df.rename(columns=str.lower)
        close = df["close"].astype(float)
        vol = df["volume"].astype(float) if "volume" in df.columns else pd.Series([1.0] * len(df))

        # G score: 변동성 역수 → 낮을수록 높은 G점수
        daily_ret = close.pct_change().dropna()
        volatility = float(daily_ret.std()) if len(daily_ret) > 1 else 0.05
        g_score = round(max(0, min(50, 50 * (1 - volatility * 10))), 1)

        # E score: 최근 가격 × 거래량 / 전체 평균 (대형주·유동성 프록시)
        turnover = float((close * vol).mean())
        avg_close = float(close.mean())
        cap_proxy = turnover / max(avg_close, 1.0)
        e_score = round(min(20, cap_proxy / 5e6 * 20), 1)

        # S score: 거래량 안정성 (표준편차/평균 역수)
        vol_cv = float(vol.std() / vol.mean()) if float(vol.mean()) > 0 else 1.0
        s_score = round(max(0, min(30, 30 * (1 - min(vol_cv, 1.0)))), 1)

        total = round(e_score + s_score + g_score, 1)
        grade = "A" if total >= 70 else "B" if total >= 50 else "C" if total >= 30 else "D"

        return {
            "ticker": ticker,
            "esg_score": total,
            "e_score": e_score,
            "s_score": s_score,
            "g_score": g_score,
            "grade": grade,
            "available": True,
            "cached_at": int(time.time()),
        }
    except Exception:
        return _empty(ticker)


def _empty(ticker: str) -> dict:
    return {
        "ticker": ticker,
        "esg_score": None,
        "e_score": None,
        "s_score": None,
        "g_score": None,
        "grade": None,
        "available": False,
        "cached_at": int(time.time()),
    }


def get_esg_score(ticker: str) -> dict:
    """종목 ESG 점수 조회 (6시간 캐시)."""
    key = ticker.upper()
    with _LOCK:
        cached = _CACHE.get(key)
        if cached and (time.time() - cached.get("cached_at", 0)) < _CACHE_TTL:
            return {**cached, "from_cache": True}

    result = _calc_esg(key)
    with _LOCK:
        _CACHE[key] = result
    return {**result, "from_cache": False}
