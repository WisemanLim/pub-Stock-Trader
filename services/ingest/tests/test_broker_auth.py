"""F1.2 브로커 인증·재연결 헬퍼 시험 (순수 함수)."""
from app.services.broker_auth import backoff_delay, build_auth_message, should_retry


def test_auth_generic():
    msg = build_auth_message("generic", "KEY", "SECRET", "005930")
    assert msg["action"] == "auth"
    assert msg["api_key"] == "KEY"
    assert msg["subscribe"] == "005930"


def test_auth_kis():
    msg = build_auth_message("kis", "APPROVAL", "SECRET", "005930")
    assert msg["header"]["approval_key"] == "APPROVAL"
    assert msg["body"]["input"]["tr_key"] == "005930"
    assert msg["body"]["input"]["tr_id"] == "H0STCNT0"


def test_backoff_exponential():
    assert backoff_delay(0, base=0.5) == 0.5
    assert backoff_delay(1, base=0.5) == 1.0
    assert backoff_delay(2, base=0.5) == 2.0
    assert backoff_delay(3, base=0.5) == 4.0


def test_backoff_capped():
    assert backoff_delay(20, base=0.5, cap=30.0) == 30.0


def test_backoff_negative_attempt():
    assert backoff_delay(-5, base=0.5) == 0.5


def test_should_retry_infinite():
    assert should_retry(100, -1) is True  # max_retries<0 → 무한


def test_should_retry_bounded():
    assert should_retry(2, 5) is True
    assert should_retry(5, 5) is False
