"""F2.1 기술지표 계산 — ta 라이브러리 기반."""
from datetime import datetime, timedelta, timezone

import FinanceDataReader as fdr
import pandas as pd
import ta


def _load_df(ticker: str, days: int) -> pd.DataFrame:
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)
    df = fdr.DataReader(ticker, start.strftime("%Y-%m-%d"))
    if df.empty:
        raise ValueError(f"No data for ticker: {ticker}")
    return df.rename(columns=str.lower)


def _signal(rsi: float | None, macd_hist: float | None) -> str:
    if rsi is None:
        return "HOLD"
    if rsi < 30:
        return "BUY"
    if rsi > 70:
        return "SELL"
    if macd_hist is not None and macd_hist > 0:
        return "BUY"
    if macd_hist is not None and macd_hist < 0:
        return "SELL"
    return "HOLD"


def compute_indicators(ticker: str, days: int = 60) -> dict:
    df = _load_df(ticker, days)
    close = df["close"]
    high = df["high"]
    low = df["low"]

    rsi_val = None
    macd_val = None
    boll_val = None
    ema20_val = None
    sma50_val = None
    atr_val = None

    if len(df) >= 14:
        rsi_ind = ta.momentum.RSIIndicator(close=close, window=14)
        r = rsi_ind.rsi().iloc[-1]
        rsi_val = round(float(r), 2) if not pd.isna(r) else None

    if len(df) >= 26:
        macd_ind = ta.trend.MACD(close=close)
        m = macd_ind.macd().iloc[-1]
        s = macd_ind.macd_signal().iloc[-1]
        h = macd_ind.macd_diff().iloc[-1]
        if not any(pd.isna(x) for x in [m, s, h]):
            macd_val = {
                "macd": round(float(m), 4),
                "signal": round(float(s), 4),
                "histogram": round(float(h), 4),
            }

    if len(df) >= 20:
        bb = ta.volatility.BollingerBands(close=close, window=20)
        u = bb.bollinger_hband().iloc[-1]
        mid = bb.bollinger_mavg().iloc[-1]
        lo = bb.bollinger_lband().iloc[-1]
        if not any(pd.isna(x) for x in [u, mid, lo]):
            bw = round((float(u) - float(lo)) / float(mid) * 100, 4) if float(mid) else 0.0
            boll_val = {
                "upper": round(float(u), 2),
                "middle": round(float(mid), 2),
                "lower": round(float(lo), 2),
                "bandwidth": bw,
            }

    if len(df) >= 20:
        ema = ta.trend.EMAIndicator(close=close, window=20).ema_indicator().iloc[-1]
        ema20_val = round(float(ema), 2) if not pd.isna(ema) else None

    if len(df) >= 50:
        sma = ta.trend.SMAIndicator(close=close, window=50).sma_indicator().iloc[-1]
        sma50_val = round(float(sma), 2) if not pd.isna(sma) else None

    if len(df) >= 14:
        atr = ta.volatility.AverageTrueRange(high=high, low=low, close=close, window=14).average_true_range().iloc[-1]
        atr_val = round(float(atr), 2) if not pd.isna(atr) else None

    # C-1: VWAP(20) — 20일 롤링 VWAP (일별 전형가 × 거래량 / 거래량합계)
    vwap_val: float | None = None
    vol_col = next((c for c in ["volume", "Volume"] if c in df.columns), None)
    if vol_col and len(df) >= 5:
        vol = df[vol_col].astype(float).replace(0, float("nan"))
        typical = (high + low + close) / 3
        window = min(20, len(df))
        tp_vol_sum = (typical * vol).rolling(window).sum()
        vol_sum = vol.rolling(window).sum()
        vwap_s = tp_vol_sum / vol_sum
        v = vwap_s.iloc[-1]
        vwap_val = round(float(v), 2) if not pd.isna(v) else None

    # C-1: 체결가 상향비율 — 당일 종가가 고저 범위에서 차지하는 위치 (0.0~1.0).
    close_pct_val: float | None = None
    if len(df) >= 1:
        c = float(close.iloc[-1])
        h = float(high.iloc[-1])
        lo = float(low.iloc[-1])
        rng = h - lo
        close_pct_val = round((c - lo) / rng, 4) if rng > 0 else 0.5

    hist = macd_val["histogram"] if macd_val else None
    return {
        "ticker": ticker,
        "timestamp": df.index[-1].strftime("%Y-%m-%dT%H:%M:%S"),
        "close": round(float(close.iloc[-1]), 2),
        "rsi": rsi_val,
        "macd": macd_val,
        "bollinger": boll_val,
        "ema_20": ema20_val,
        "sma_50": sma50_val,
        "atr": atr_val,
        "vwap_20": vwap_val,
        "close_pct": close_pct_val,
        "signal": _signal(rsi_val, hist),
    }
