"""C-2: 시장 폭(Market Breadth) 지표 — 상승/하락 종목수·TRIN·AD Line.

30분 캐시. 샘플 100종목 기준 (속도 vs 정확도 균형).
"""
import threading
import time
from datetime import datetime, timedelta, timezone

import FinanceDataReader as fdr
import pandas as pd

_LOCK = threading.Lock()
_CACHE: dict[str, dict] = {}
_CACHE_TTL = 1800  # 30분


def _fetch_breadth(market: str, sample: int = 100) -> dict:
    """상장 종목 sample개의 당일 등락 집계."""
    try:
        listing = fdr.StockListing(market)
    except Exception:
        return _empty(market)

    code_col = next((c for c in ["Code", "Symbol"] if c in listing.columns), None)
    if code_col is None:
        return _empty(market)

    tickers = listing[code_col].head(sample).tolist()
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=5)
    start_str = start.strftime("%Y-%m-%d")

    advancing = 0
    declining = 0
    unchanged = 0
    adv_vol = 0.0
    dec_vol = 0.0
    ad_raw: list[int] = []

    for tk in tickers:
        try:
            df = fdr.DataReader(str(tk), start_str)
            if len(df) < 2:
                continue
            df = df.rename(columns=str.lower)
            closes = df["close"].astype(float)
            chg = float(closes.iloc[-1]) - float(closes.iloc[-2])
            vol = float(df["volume"].iloc[-1]) if "volume" in df.columns else 0.0
            if chg > 0:
                advancing += 1
                adv_vol += vol
            elif chg < 0:
                declining += 1
                dec_vol += vol
            else:
                unchanged += 1
        except Exception:
            continue

    # AD Line = 누적 (상승 - 하락) for this sample
    ad_line = advancing - declining

    # TRIN(Arms Index) = (A/D) / (Avg_Vol_A / Avg_Vol_D). 1 미만 → 강세.
    trin: float | None = None
    if declining > 0 and dec_vol > 0 and adv_vol > 0 and advancing > 0:
        ad_ratio = advancing / declining
        vol_ratio = (adv_vol / advancing) / (dec_vol / declining)
        trin = round(ad_ratio / vol_ratio, 4) if vol_ratio else None

    total = advancing + declining + unchanged
    return {
        "market": market,
        "sample": total,
        "advancing": advancing,
        "declining": declining,
        "unchanged": unchanged,
        "ad_line": ad_line,
        "trin": trin,
        "cached_at": int(time.time()),
    }


def _empty(market: str) -> dict:
    return {
        "market": market,
        "sample": 0,
        "advancing": 0,
        "declining": 0,
        "unchanged": 0,
        "ad_line": 0,
        "trin": None,
        "cached_at": int(time.time()),
    }


def get_breadth(market: str) -> dict:
    key = market.upper()
    with _LOCK:
        cached = _CACHE.get(key)
        if cached and (time.time() - cached.get("cached_at", 0)) < _CACHE_TTL:
            return {**cached, "from_cache": True}

    result = _fetch_breadth(key)
    with _LOCK:
        _CACHE[key] = result
    return {**result, "from_cache": False}
