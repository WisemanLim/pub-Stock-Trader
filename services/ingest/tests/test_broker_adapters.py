"""F1.2 브로커 프로토콜 어댑터 시험 — 메시지 정규화."""
import json

import pytest

from app.services.broker_adapters import get_adapter, list_adapters, register_adapter


def test_list_adapters():
    a = list_adapters()
    assert "generic" in a
    assert "kis" in a


def test_generic_json():
    adapter = get_adapter("generic")
    raw = json.dumps({"price": 73500.0, "change_pct": 1.2})
    tick = adapter("005930", raw)
    assert tick["ticker"] == "005930"
    assert tick["price"] == 73500.0
    assert tick["change_pct"] == 1.2
    assert tick["source"] == "broker:generic"


def test_generic_invalid_json_returns_none():
    adapter = get_adapter("generic")
    assert adapter("005930", "not json") is None


def test_generic_missing_price_returns_none():
    adapter = get_adapter("generic")
    assert adapter("005930", json.dumps({"volume": 100})) is None


def test_kis_text_format():
    adapter = get_adapter("kis")
    # 종목^시각^현재가^...^...^등락률
    raw = "0|H0STCNT0|001|005930^123005^73500^0^0^1.5"
    tick = adapter("005930", raw)
    assert tick["ticker"] == "005930"
    assert tick["price"] == 73500.0
    assert tick["change_pct"] == 1.5
    assert tick["source"] == "broker:kis"


def test_kis_json_format():
    adapter = get_adapter("kis")
    raw = json.dumps({"body": {"stck_prpr": "73500", "prdy_ctrt": "1.5"}})
    tick = adapter("005930", raw)
    assert tick["price"] == 73500.0
    assert tick["change_pct"] == 1.5


def test_kis_malformed_returns_none():
    adapter = get_adapter("kis")
    assert adapter("005930", "0|H0STCNT0|001|005930") is None  # 필드 부족


def test_unknown_adapter_raises():
    with pytest.raises(ValueError):
        get_adapter("nonexistent")


def test_register_custom_adapter():
    register_adapter("custom_t", lambda t, r: {"ticker": t, "price": 1.0,
                                               "change_pct": 0.0, "timestamp": "x", "source": "custom"})
    tick = get_adapter("custom_t")("AAA", "anything")
    assert tick["source"] == "custom"
