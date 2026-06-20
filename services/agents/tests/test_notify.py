"""F6.3 알림 시험 — webhook mock / no-op 폴백."""
from unittest.mock import patch


def test_notify_noop_when_unconfigured(client):
    """토큰 미설정 → 채널 false, 200 정상(no-op)."""
    r = client.post("/notify/", json={"event": "TEST", "payload": {"ticker": "005930"}})
    assert r.status_code == 200
    data = r.json()
    assert data["telegram"] is False
    assert data["discord"] is False
    assert "005930" in data["message"]


def test_notify_message_format(client):
    r = client.post("/notify/", json={"event": "STOP_LOSS", "payload": {"price": 68000}})
    msg = r.json()["message"]
    assert "STOP_LOSS" in msg
    assert "price: 68000" in msg


def test_notify_discord_success(client):
    class FakeResp:
        status_code = 204

    with patch("app.services.notifier.settings.discord_webhook_url", "https://discord/x"), \
         patch("app.services.notifier.httpx.post", return_value=FakeResp()):
        r = client.post("/notify/", json={"event": "BUY", "payload": {}})
    assert r.json()["discord"] is True
