"""D-4: 분봉 기반 기술지표 계산 — RSI·MACD·VWAP (1분/5분)."""
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import pandas as pd
import ta

_INGEST_URL = "http://localhost:8003"
_CACHE: dict[str, dict] = {}
_LOCK = threading.Lock()
_CACHE_TTL = 60  # 1분


def _fetch_bars(ticker: str, interval: str) -> list[dict]:
    import httpx
    try:
        r = httpx.get(f"{_INGEST_URL}/market/intraday/{ticker}?interval={interval}", timeout=5.0)
        if r.status_code == 200:
            return r.json().get("bars", [])
    except Exception:
        pass
    return []


def calc_intraday_indicators(ticker: str, interval: str = "5m") -> dict:
    """분봉 데이터로 RSI·MACD·VWAP 계산. ingest 분봉 API 의존."""
    if interval not in ("1m", "5m"):
        interval = "5m"

    key = f"{ticker.upper()}:{interval}"
    with _LOCK:
        cached = _CACHE.get(key)
        if cached and (time.time() - cached.get("_cached_at", 0)) < _CACHE_TTL:
            return {k: v for k, v in cached.items() if k != "_cached_at"}

    bars = _fetch_bars(ticker.upper(), interval)
    if len(bars) < 14:
        result: dict[str, Any] = {
            "ticker": ticker.upper(),
            "interval": interval,
            "available": False,
        }
        with _LOCK:
            _CACHE[key] = {**result, "_cached_at": int(time.time())}
        return result

    df = pd.DataFrame(bars)
    close = df["close"].astype(float)
    high = df["high"].astype(float)
    low = df["low"].astype(float)
    vol = df["volume"].astype(float) if "volume" in df.columns else pd.Series([1.0] * len(df))

    # RSI(14)
    rsi_val = None
    try:
        rsi_series = ta.momentum.RSIIndicator(close=close, window=14).rsi()
        v = rsi_series.iloc[-1]
        rsi_val = round(float(v), 2) if not pd.isna(v) else None
    except Exception:
        pass

    # MACD(12,26,9)
    macd_val = None
    try:
        m = ta.trend.MACD(close=close, window_slow=26, window_fast=12, window_sign=9)
        mv = m.macd().iloc[-1]
        sv = m.macd_signal().iloc[-1]
        hv = m.macd_diff().iloc[-1]
        macd_val = {
            "macd": round(float(mv), 4) if not pd.isna(mv) else None,
            "signal": round(float(sv), 4) if not pd.isna(sv) else None,
            "histogram": round(float(hv), 4) if not pd.isna(hv) else None,
        }
    except Exception:
        pass

    # VWAP (cumulative intraday)
    vwap_val = None
    try:
        typical = (high + low + close) / 3
        cum_tp_vol = (typical * vol).cumsum()
        cum_vol = vol.cumsum()
        vwap_series = cum_tp_vol / cum_vol
        v = vwap_series.iloc[-1]
        vwap_val = round(float(v), 2) if not pd.isna(v) else None
    except Exception:
        pass

    signal = "HOLD"
    if rsi_val is not None:
        if rsi_val < 30:
            signal = "BUY"
        elif rsi_val > 70:
            signal = "SELL"

    result = {
        "ticker": ticker.upper(),
        "interval": interval,
        "available": True,
        "close": round(float(close.iloc[-1]), 2),
        "rsi": rsi_val,
        "macd": macd_val,
        "vwap": vwap_val,
        "signal": signal,
        "bar_count": len(bars),
    }
    with _LOCK:
        _CACHE[key] = {**result, "_cached_at": int(time.time())}
    return result
