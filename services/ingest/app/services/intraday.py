"""D-3: 분봉(1분/5분) 데이터 수집 — FinanceDataReader + Naver Finance 폴백.

KRX 직접 분봉 API는 유료/인증 필요. FDR 경유 naver 분봉 지원 여부를 먼저 시도하고,
실패 시 최근 일봉을 30분봉으로 다운샘플링해 반환한다(fallback).
"""
import threading
import time
from datetime import datetime, timedelta, timezone

import FinanceDataReader as fdr
import pandas as pd

_CACHE: dict[str, dict] = {}
_LOCK = threading.Lock()
_CACHE_TTL_1M = 60      # 1분봉: 60초 캐시
_CACHE_TTL_5M = 300     # 5분봉: 5분 캐시


def _resample_daily_to_bars(ticker: str, interval: str) -> list[dict]:
    """일봉 → 분봉 근사 다운샘플링 (fallback).

    실제 분봉 대신 최근 5일 일봉을 N분 단위로 분해 (OHLCV 유지).
    프로덕션에서는 KIS REST API나 eBEST xingAPI로 교체.
    """
    try:
        end = datetime.now(timezone.utc)
        start = end - timedelta(days=5)
        df = fdr.DataReader(ticker, start.strftime("%Y-%m-%d"))
        if df.empty:
            return []
        df = df.rename(columns=str.lower)
        freq = "5T" if interval == "5m" else "1T"
        rows = []
        for _, row in df.tail(3).iterrows():
            idx_date = getattr(row.name, 'date', lambda: None)()
            if idx_date is None:
                continue
            # spread OHLCV across the day's bars (9:00 ~ 15:30 KST)
            open_t = datetime(idx_date.year, idx_date.month, idx_date.day, 9, 0)
            end_t = datetime(idx_date.year, idx_date.month, idx_date.day, 15, 30)
            current = open_t
            delta = timedelta(minutes=5 if interval == "5m" else 1)
            close_v = float(row.get("close", 0))
            open_v = float(row.get("open", close_v))
            high_v = float(row.get("high", close_v))
            low_v = float(row.get("low", close_v))
            vol_total = int(row.get("volume", 0))
            slot_count = int((end_t - open_t).total_seconds() / delta.total_seconds())
            vol_per = vol_total // max(slot_count, 1) if slot_count else 0
            bar_range = (high_v - low_v) / max(slot_count, 1) * 2
            bar_idx = 0
            while current < end_t:
                # 일봉 open→close 선형 보간으로 현실적인 분봉 생성
                t = bar_idx / max(slot_count - 1, 1)
                t_prev = max(bar_idx - 1, 0) / max(slot_count - 1, 1)
                bar_o = round(open_v + (close_v - open_v) * t_prev, 2)
                bar_c = round(open_v + (close_v - open_v) * t, 2)
                bar_h = round(min(high_v, max(bar_o, bar_c) + bar_range), 2)
                bar_l = round(max(low_v, min(bar_o, bar_c) - bar_range), 2)
                rows.append({
                    "datetime": current.strftime("%Y-%m-%d %H:%M"),
                    "open": bar_o,
                    "high": bar_h,
                    "low": bar_l,
                    "close": bar_c,
                    "volume": vol_per,
                })
                current += delta
                bar_idx += 1
        return rows[-100:]  # 최신 100봉
    except Exception:
        return []


def fetch_intraday(ticker: str, interval: str = "5m") -> dict:
    """분봉 데이터 조회. interval: '1m' | '5m'."""
    if interval not in ("1m", "5m"):
        interval = "5m"

    ttl = _CACHE_TTL_1M if interval == "1m" else _CACHE_TTL_5M
    key = f"{ticker.upper()}:{interval}"

    with _LOCK:
        cached = _CACHE.get(key)
        if cached and (time.time() - cached.get("cached_at", 0)) < ttl:
            return {**cached, "from_cache": True}

    # FDR 분봉 시도 (지원 ticker/provider에서만 성공)
    bars: list[dict] = []
    source = "fallback"
    try:
        df = fdr.DataReader(ticker, pd.Timestamp.now() - pd.Timedelta("1d"), interval=interval)
        if not df.empty:
            df = df.rename(columns=str.lower)
            bars = [
                {
                    "datetime": str(idx),
                    "open": float(r.get("open", 0)),
                    "high": float(r.get("high", 0)),
                    "low": float(r.get("low", 0)),
                    "close": float(r.get("close", 0)),
                    "volume": int(r.get("volume", 0)),
                }
                for idx, r in df.iterrows()
            ][-100:]
            source = "fdr"
    except Exception:
        pass

    if not bars:
        bars = _resample_daily_to_bars(ticker, interval)
        source = "fallback_daily"

    result = {
        "ticker": ticker.upper(),
        "interval": interval,
        "count": len(bars),
        "bars": bars,
        "source": source,
        "cached_at": int(time.time()),
    }
    with _LOCK:
        _CACHE[key] = result
    return {**result, "from_cache": False}
