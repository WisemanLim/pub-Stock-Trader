"""F1.2 브로커 토큰 만료·재발급 시험 (주입 시계)."""
from app.services.broker_token import TokenManager


class FakeClock:
    def __init__(self, t=0.0):
        self.t = t

    def __call__(self):
        return self.t


def test_first_get_issues_token():
    clock = FakeClock(0.0)
    tm = TokenManager(lambda: ("tok1", 3600), skew_seconds=60, now_fn=clock)
    assert tm.get_token() == "tok1"
    assert tm.issue_count == 1


def test_cached_token_reused():
    clock = FakeClock(0.0)
    seq = iter(["tok1", "tok2"])
    tm = TokenManager(lambda: (next(seq), 3600), skew_seconds=60, now_fn=clock)
    tm.get_token()
    clock.t = 100.0  # 아직 만료 전
    assert tm.get_token() == "tok1"  # 재사용
    assert tm.issue_count == 1


def test_token_refreshed_after_expiry():
    clock = FakeClock(0.0)
    seq = iter(["tok1", "tok2"])
    tm = TokenManager(lambda: (next(seq), 3600), skew_seconds=60, now_fn=clock)
    tm.get_token()
    clock.t = 3600.0  # 만료 시점(skew 고려 시 이미 만료)
    assert tm.get_token() == "tok2"  # 재발급
    assert tm.issue_count == 2


def test_skew_triggers_early_refresh():
    clock = FakeClock(0.0)
    seq = iter(["tok1", "tok2"])
    tm = TokenManager(lambda: (next(seq), 3600), skew_seconds=60, now_fn=clock)
    tm.get_token()
    clock.t = 3541.0  # 만료 59초 전 → skew 60 이내 → 재발급
    assert tm.get_token() == "tok2"
    assert tm.issue_count == 2


def test_invalidate_forces_reissue():
    clock = FakeClock(0.0)
    seq = iter(["tok1", "tok2"])
    tm = TokenManager(lambda: (next(seq), 3600), skew_seconds=60, now_fn=clock)
    tm.get_token()
    tm.invalidate()
    assert tm.get_token() == "tok2"  # 401 등으로 강제 재발급
    assert tm.issue_count == 2


def test_is_expired_initially_true():
    tm = TokenManager(lambda: ("t", 100), now_fn=FakeClock(0.0))
    assert tm.is_expired() is True
