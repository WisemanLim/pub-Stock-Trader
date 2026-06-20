"""F6.3 양방향 제어 시험 — 인바운드 명령 인증·파싱·risk-engine 위임."""
import pytest
from fastapi.testclient import TestClient

from app.services.control import parse_command


def test_parse_command_valid():
    assert parse_command("/stop") == "/stop"
    assert parse_command("/LIQUIDATE now") == "/liquidate"  # 대소문자·인자 허용


def test_parse_command_invalid():
    assert parse_command("hello") is None
    assert parse_command("") is None


class FakeResp:
    def __init__(self, payload):
        self._p = payload

    def json(self):
        return self._p


@pytest.fixture
def control_client(monkeypatch):
    """control_secret 설정 + risk-engine httpx mock."""
    import app.services.control as ctrl
    monkeypatch.setattr(ctrl.settings, "control_secret", "s3cret")

    def _fake_get(url, timeout=5.0):
        return FakeResp({"halted": False, "open_positions": 2})

    def _fake_post(url, json=None, timeout=5.0):
        if url.endswith("/control/halt"):
            return FakeResp({"halted": json["halted"]})
        if url.endswith("/control/liquidate"):
            return FakeResp({"liquidated": 2, "realized_pnl": 1000.0, "halted": True})
        return FakeResp({})

    monkeypatch.setattr(ctrl.httpx, "get", _fake_get)
    monkeypatch.setattr(ctrl.httpx, "post", _fake_post)
    from app.main import app
    with TestClient(app) as c:
        yield c


def test_command_unauthorized_when_no_secret(control_client):
    r = control_client.post("/control/command", json={"text": "/stop"})
    assert r.status_code == 403


def test_command_unauthorized_wrong_secret(control_client):
    r = control_client.post("/control/command", json={"secret": "nope", "text": "/stop"})
    assert r.status_code == 403


def test_command_stop_halts(control_client):
    r = control_client.post("/control/command", json={"secret": "s3cret", "text": "/stop"})
    assert r.status_code == 200
    assert r.json()["result"]["halted"] is True


def test_command_resume(control_client):
    r = control_client.post("/control/command", json={"secret": "s3cret", "text": "/resume"})
    assert r.json()["result"]["halted"] is False


def test_command_liquidate(control_client):
    r = control_client.post("/control/command", json={
        "secret": "s3cret", "text": "/liquidate",
        "prices": {"005930": 71000.0},
    })
    assert r.json()["result"]["liquidated"] == 2


def test_command_status(control_client):
    r = control_client.post("/control/command", json={"secret": "s3cret", "text": "/status"})
    assert r.json()["result"]["open_positions"] == 2


def test_command_unknown(control_client):
    r = control_client.post("/control/command", json={"secret": "s3cret", "text": "/blowup"})
    assert r.status_code == 400


def test_telegram_webhook(control_client):
    r = control_client.post(
        "/control/telegram?secret=s3cret",
        json={"message": {"text": "/stop"}},
    )
    assert r.status_code == 200
    assert r.json()["result"]["halted"] is True


def test_telegram_header_secret(control_client):
    r = control_client.post(
        "/control/telegram",
        json={"message": {"text": "/status"}},
        headers={"X-Telegram-Bot-Api-Secret-Token": "s3cret"},
    )
    assert r.status_code == 200


def test_secret_unset_rejects_all(monkeypatch):
    """control_secret 미설정 → 모든 인바운드 제어 거부(안전 기본)."""
    import app.services.control as ctrl
    monkeypatch.setattr(ctrl.settings, "control_secret", "")
    from app.main import app
    with TestClient(app) as c:
        r = c.post("/control/command", json={"secret": "", "text": "/stop"})
        assert r.status_code == 403
