"""F1.2 브로커 하트비트 핑퐁 시험 (주입 시계)."""
from app.services.broker_heartbeat import (
    HeartbeatMonitor,
    build_ping_message,
    is_pong,
)


class FakeClock:
    def __init__(self, t=0.0):
        self.t = t

    def __call__(self):
        return self.t


def test_ping_message_generic():
    assert build_ping_message("generic") == {"action": "ping"}


def test_ping_message_kis():
    assert build_ping_message("kis")["header"]["tr_id"] == "PINGPONG"


def test_is_pong_generic():
    assert is_pong("generic", {"action": "pong"}) is True
    assert is_pong("generic", {"type": "pong"}) is True
    assert is_pong("generic", {"price": 100}) is False


def test_is_pong_kis():
    assert is_pong("kis", {"header": {"tr_id": "PINGPONG"}}) is True
    assert is_pong("kis", {"header": {"tr_id": "H0STCNT0"}}) is False


def test_should_ping_after_interval():
    clock = FakeClock(0.0)
    hb = HeartbeatMonitor(interval=20, timeout=60, now_fn=clock)
    assert hb.should_ping() is False
    clock.t = 20.0
    assert hb.should_ping() is True
    hb.mark_ping()
    assert hb.should_ping() is False


def test_stale_after_timeout():
    clock = FakeClock(0.0)
    hb = HeartbeatMonitor(interval=20, timeout=60, now_fn=clock)
    clock.t = 61.0
    assert hb.is_stale() is True


def test_activity_resets_stale():
    clock = FakeClock(0.0)
    hb = HeartbeatMonitor(interval=20, timeout=60, now_fn=clock)
    clock.t = 50.0
    hb.record_activity()
    clock.t = 100.0  # 활동 후 50초 → timeout 60 미만
    assert hb.is_stale() is False
