"""F1.2 호가창 서비스 — 브로커 API 미연결 시 가격 기반 시뮬레이션."""
from datetime import datetime, timezone

from app.services.finance_reader import FinanceReaderService

_fdr = FinanceReaderService()

_TICK_SIZES = {
    "default": 5,
    "large": 100,
}


def _tick(price: float) -> int:
    if price >= 500_000:
        return 1_000
    if price >= 100_000:
        return 500
    if price >= 50_000:
        return 100
    if price >= 10_000:
        return 50
    if price >= 5_000:
        return 10
    return 5


def get_orderbook(ticker: str, levels: int = 10) -> dict:
    """마지막 종가 기반 가상 호가창 (10/20 레벨)."""
    data = _fdr.get_price(ticker)
    mid = data["price"]
    tick = _tick(mid)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")

    import random
    rng = random.Random(hash(ticker + now[:13]))

    asks, bids = [], []
    for i in range(1, levels + 1):
        ask_px = round(mid + i * tick, 2)
        bid_px = round(mid - i * tick, 2)
        asks.append({
            "price": ask_px,
            "quantity": rng.randint(100, 5000),
            "count": rng.randint(1, 20),
        })
        bids.append({
            "price": bid_px,
            "quantity": rng.randint(100, 5000),
            "count": rng.randint(1, 20),
        })

    best_ask = asks[0]["price"]
    best_bid = bids[0]["price"]
    return {
        "ticker": ticker,
        "timestamp": now,
        "ask_levels": asks,
        "bid_levels": bids,
        "spread": round(best_ask - best_bid, 2),
        "mid_price": round((best_ask + best_bid) / 2, 2),
        "source": "simulated",
    }
