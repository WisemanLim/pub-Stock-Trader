"""F1.2 적응형 흐름제어 시험 — AIMD · 우선순위 큐 · 백프레셔."""
import pytest

from app.services.adaptive_flow import AIMDRateController, PriorityCommandQueue


# ── AIMD ──

def test_aimd_additive_increase():
    c = AIMDRateController(base_rate=10.0, ai_step=2.0)
    assert c.on_success() == 12.0
    assert c.on_success() == 14.0


def test_aimd_multiplicative_decrease():
    c = AIMDRateController(base_rate=10.0, md_factor=0.5)
    assert c.on_loss() == 5.0
    assert c.on_loss() == 2.5


def test_aimd_clamps_max():
    c = AIMDRateController(base_rate=99.0, ai_step=5.0, max_rate=100.0)
    assert c.on_success() == 100.0
    assert c.on_success() == 100.0  # 상한 유지


def test_aimd_clamps_min():
    c = AIMDRateController(base_rate=2.0, md_factor=0.5, min_rate=1.0)
    c.on_loss()              # 1.0
    assert c.on_loss() == 1.0  # 하한 유지


def test_aimd_sawtooth():
    """전형 톱니파: 증가 누적 후 손실 시 급감."""
    c = AIMDRateController(base_rate=10.0, ai_step=1.0, md_factor=0.5, min_rate=1.0, max_rate=100.0)
    for _ in range(5):
        c.on_success()       # 15.0
    assert c.current_rate() == 15.0
    assert c.on_loss() == 7.5


def test_aimd_invalid_md_factor():
    with pytest.raises(ValueError):
        AIMDRateController(base_rate=10.0, md_factor=1.5)


# ── 우선순위 큐 ──

def test_priority_order():
    q = PriorityCommandQueue()
    q.push("low", priority=1)
    q.push("high", priority=10)
    q.push("mid", priority=5)
    assert q.pop() == "high"
    assert q.pop() == "mid"
    assert q.pop() == "low"


def test_priority_fifo_within_same_level():
    q = PriorityCommandQueue()
    q.push("a", priority=5)
    q.push("b", priority=5)
    q.push("c", priority=5)
    assert [q.pop(), q.pop(), q.pop()] == ["a", "b", "c"]


def test_pop_empty_returns_none():
    assert PriorityCommandQueue().pop() is None


def test_drain_priority_order():
    q = PriorityCommandQueue()
    q.push("x", priority=1)
    q.push("y", priority=9)
    assert q.drain() == ["y", "x"]
    assert len(q) == 0


# ── 백프레셔 ──

def test_backpressure_watermark():
    q = PriorityCommandQueue(high_watermark=2)
    assert q.is_backpressured() is False
    q.push("a", priority=1)
    assert q.is_backpressured() is False
    q.push("b", priority=1)
    assert q.is_backpressured() is True   # 워터마크 도달


def test_capacity_drops_lowest_priority():
    q = PriorityCommandQueue(capacity=2)
    assert q.push("keep-hi", priority=10) is None
    assert q.push("keep-mid", priority=5) is None
    # 용량 초과 → 최저 우선순위 드롭. low(1) 가 victim.
    dropped = q.push("low", priority=1)
    assert dropped == "low"
    assert q.dropped == 1
    # 남은 것은 우선순위 높은 둘.
    assert set(q.drain()) == {"keep-hi", "keep-mid"}


def test_capacity_drops_existing_when_new_higher():
    q = PriorityCommandQueue(capacity=1)
    q.push("low", priority=1)
    dropped = q.push("high", priority=10)  # 용량1 초과 → 최저(low) 드롭
    assert dropped == "low"
    assert q.pop() == "high"


def test_no_backpressure_when_unbounded():
    q = PriorityCommandQueue()
    for i in range(100):
        q.push(i, priority=0)
    assert q.is_backpressured() is False
    assert q.dropped == 0
