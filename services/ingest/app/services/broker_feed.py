"""F1.2 브로커 실시간 피드 — WebSocket 실연동 + 시뮬레이션 폴백.

BROKER_WS_URL 설정 시 브로커 WS 연결(증권사 틱 스트림),
미설정 시 마지막 종가 기반 random-walk 시뮬레이션 틱 생성.
실 키는 OS Keychain/Vault — 이 모듈은 URL 만 사용(시크릿 미보관).
"""
import asyncio
import json
import random
from datetime import datetime, timezone

from app.core.config import settings
from app.services.finance_reader import FinanceReaderService

_fdr = FinanceReaderService()


def simulate_tick(prev_price: float, rng: random.Random) -> dict:
    """random-walk 한 스텝 — 순수 함수(테스트 가능). ±0.3% 변동."""
    drift = rng.uniform(-0.003, 0.003)
    price = round(prev_price * (1 + drift), 2)
    return {
        "price": price,
        "change_pct": round(drift * 100, 4),
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"),
        "source": "simulated",
    }


async def _simulated_stream(ticker: str, interval: float, rng: random.Random):
    """브로커 미연결 시 시세 기반 모의 틱 스트림."""
    try:
        prev = _fdr.get_price(ticker)["price"]
    except Exception:
        prev = 10000.0
    while True:
        tick = simulate_tick(prev, rng)
        tick["ticker"] = ticker
        prev = tick["price"]
        yield tick
        await asyncio.sleep(interval)


async def _simulated_multi(tickers: list[str], interval: float, rng: random.Random):
    """다종목 시뮬 — 종목별 가격 유지하며 라운드로빈 틱 방출."""
    prev: dict[str, float] = {}
    for t in tickers:
        try:
            prev[t] = _fdr.get_price(t)["price"]
        except Exception:
            prev[t] = 10000.0
    while True:
        for t in tickers:
            tick = simulate_tick(prev[t], rng)
            tick["ticker"] = t
            prev[t] = tick["price"]
            yield tick
        await asyncio.sleep(interval)


def feed_multi(tickers: list[str], interval: float = 1.0, rng: random.Random | None = None):
    """다종목 피드 — BROKER_WS_URL 있으면 실 멀티플렉싱, 없으면 시뮬."""
    if settings.broker_ws_url:
        return _broker_multi_stream(tickers, settings.broker_ws_url)
    return _simulated_multi(tickers, interval, rng or random.Random())


async def _broker_multi_stream(tickers: list[str], url: str):
    """실 브로커 단일 WS — 다종목 구독 후 어댑터로 틱 라우팅."""
    import websockets

    from app.services.broker_adapters import get_adapter
    from app.services.broker_multiplex import MultiplexRouter, build_subscribe_messages

    proto = settings.broker_protocol
    adapter = get_adapter(proto)
    router = MultiplexRouter()
    for t in tickers:
        router.subscribe(t)
    subs = build_subscribe_messages(proto, settings.broker_api_key, settings.broker_api_secret, tickers)
    async with websockets.connect(url) as ws:
        for m in subs:
            await ws.send(json.dumps(m))
        async for raw in ws:
            text = raw if isinstance(raw, str) else raw.decode()
            # 어댑터는 단일 ticker 인자를 받으므로 메시지에서 추출 위해 각 종목 시도
            for t in tickers:
                tick = adapter(t, text)
                if tick is not None and router.dispatch(tick):
                    yield tick
                    break


async def _broker_connect_once(ticker: str, url: str):
    """1회 연결 — 인증 핸드셰이크 + 하트비트 핑퐁 후 틱 스트림."""
    import websockets

    from app.services.broker_adapters import get_adapter
    from app.services.broker_auth import build_auth_message
    from app.services.broker_heartbeat import HeartbeatMonitor, build_ping_message, is_pong

    proto = settings.broker_protocol
    adapter = get_adapter(proto)
    auth_msg = build_auth_message(proto, settings.broker_api_key, settings.broker_api_secret, ticker)
    hb = HeartbeatMonitor(
        interval=settings.broker_heartbeat_interval,
        timeout=settings.broker_heartbeat_timeout,
    )
    async with websockets.connect(url) as ws:
        await ws.send(json.dumps(auth_msg))  # 인증 + 구독
        while True:
            if hb.is_stale():  # 무활동 timeout → 끊고 재연결
                break
            if hb.should_ping():
                await ws.send(json.dumps(build_ping_message(proto)))
                hb.mark_ping()
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=hb._interval)
            except asyncio.TimeoutError:
                continue  # 수신 없음 → 루프 재진입(ping/stale 검사)
            hb.record_activity()
            text = raw if isinstance(raw, str) else raw.decode()
            try:
                if is_pong(proto, json.loads(text)):
                    continue  # pong → 활동만 기록
            except (json.JSONDecodeError, AttributeError):
                pass
            tick = adapter(ticker, text)
            if tick is not None:
                yield tick


async def _broker_stream(ticker: str, url: str):
    """재연결 래퍼 — 끊기면 지수 백오프 후 재접속(인증 재수행)."""
    from app.services.broker_auth import backoff_delay, should_retry

    attempt = 0
    while True:
        try:
            async for tick in _broker_connect_once(ticker, url):
                attempt = 0  # 정상 수신 시 백오프 리셋
                yield tick
            # 스트림 정상 종료 → 재연결 시도
        except Exception:
            pass  # 연결 오류 → 재연결
        if not should_retry(attempt, settings.broker_max_retries):
            break
        await asyncio.sleep(backoff_delay(attempt))
        attempt += 1


def feed(ticker: str, interval: float = 1.0, rng: random.Random | None = None):
    """피드 선택 — BROKER_WS_URL 있으면 실연동, 없으면 시뮬레이션."""
    if settings.broker_ws_url:
        return _broker_stream(ticker, settings.broker_ws_url)
    return _simulated_stream(ticker, interval, rng or random.Random())
