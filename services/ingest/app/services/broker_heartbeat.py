"""F1.2 브로커 하트비트 핑퐁 — WS keepalive (순수 헬퍼, 테스트 가능).

interval 마다 ping 송신, timeout 내 pong/활동 없으면 stale(재연결 트리거).
now_fn 주입으로 시계 테스트 가능. 브로커별 ping/pong 포맷은 protocol 분기.
"""
import time
from typing import Callable


def build_ping_message(protocol: str) -> dict:
    if protocol == "kis":
        return {"header": {"tr_id": "PINGPONG"}}
    return {"action": "ping"}


def is_pong(protocol: str, msg: dict) -> bool:
    if protocol == "kis":
        return msg.get("header", {}).get("tr_id") == "PINGPONG"
    return msg.get("action") == "pong" or msg.get("type") == "pong"


class HeartbeatMonitor:
    def __init__(
        self,
        interval: float = 20.0,   # ping 주기(초)
        timeout: float = 60.0,    # 무활동 → stale 판정(초)
        now_fn: Callable[[], float] = time.time,
    ) -> None:
        self._interval = interval
        self._timeout = timeout
        self._now = now_fn
        t = self._now()
        self._last_activity = t   # 마지막 수신(틱/pong)
        self._last_ping = t

    def record_activity(self) -> None:
        """틱·pong 등 수신 시 호출 → 활동 시각 갱신."""
        self._last_activity = self._now()

    def should_ping(self) -> bool:
        """마지막 ping 후 interval 경과 → ping 송신 시점."""
        return (self._now() - self._last_ping) >= self._interval

    def mark_ping(self) -> None:
        self._last_ping = self._now()

    def is_stale(self) -> bool:
        """마지막 활동 후 timeout 초과 → 연결 죽음(재연결 필요)."""
        return (self._now() - self._last_activity) > self._timeout
