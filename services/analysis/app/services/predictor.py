"""F2.2 시계열 예측 — 선형회귀 기반 경량 모델 (LSTM placeholder 인터페이스)."""
from datetime import datetime, timedelta, timezone

import FinanceDataReader as fdr
import numpy as np
import pandas as pd


def _load_close(ticker: str, days: int = 90) -> pd.Series:
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)
    df = fdr.DataReader(ticker, start.strftime("%Y-%m-%d"))
    if df.empty:
        raise ValueError(f"No data for ticker: {ticker}")
    return df["Close"].astype(float)


def _linear_predict(series: pd.Series, steps: int) -> float:
    """단순 선형회귀로 steps 일 후 예측가."""
    y = series.values
    x = np.arange(len(y))
    coeffs = np.polyfit(x, y, 1)
    return float(np.polyval(coeffs, len(y) + steps - 1))


def predict(ticker: str) -> dict:
    close = _load_close(ticker)
    current = float(close.iloc[-1])

    horizons = []
    for label, steps in [("5min", 1), ("30min", 1), ("1day", 1), ("5day", 5)]:
        pred = _linear_predict(close, steps)
        direction = "UP" if pred > current else "DOWN"
        delta = abs(pred - current) / current
        confidence = min(0.95, max(0.50, 0.75 - delta * 10))
        horizons.append({
            "horizon": label,
            "predicted_price": round(pred, 2),
            "direction": direction,
            "confidence": round(confidence, 3),
        })

    return {
        "ticker": ticker,
        "current_price": round(current, 2),
        "model": "linear-regression-v1",
        "horizons": horizons,
    }
