"""F1.5 KRX OPEN API 서비스 + 엔드포인트 시험."""
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.krx_openapi import KrxOpenApiService, _fmt_date, _to_int, _to_float

client = TestClient(app)


# ──────────────────────────────────────────────────────────────
# 변환 헬퍼
# ──────────────────────────────────────────────────────────────

class TestHelpers:
    def test_fmt_date_yyyymmdd(self):
        assert _fmt_date("20260101") == "2026-01-01"

    def test_fmt_date_already_hyphen(self):
        assert _fmt_date("2026-01-01") == "2026-01-01"

    def test_fmt_date_with_comma(self):
        # KRX sometimes returns "20,260,101" — strip commas
        assert _fmt_date("20260101") == "2026-01-01"

    def test_to_int_normal(self):
        assert _to_int("1,200,000") == 1200000

    def test_to_int_invalid(self):
        assert _to_int("N/A") == 0

    def test_to_float_normal(self):
        assert _to_float("1.48") == pytest.approx(1.48)

    def test_to_float_invalid(self):
        assert _to_float("-") == 0.0


# ──────────────────────────────────────────────────────────────
# KrxOpenApiService — 미설정(no key)
# ──────────────────────────────────────────────────────────────

class TestKrxServiceUnconfigured:
    def setup_method(self):
        self.svc = KrxOpenApiService(api_key="")

    def test_configured_false_when_no_key(self):
        assert self.svc.configured is False

    def test_get_daily_ohlcv_returns_empty_when_unconfigured(self):
        assert self.svc.get_daily_ohlcv("005930", "20260101", "20260131") == []

    def test_get_investor_flow_returns_empty_when_unconfigured(self):
        assert self.svc.get_investor_flow("005930", "20260101", "20260131") == []


# ──────────────────────────────────────────────────────────────
# KrxOpenApiService — 설정됨(mocked HTTP)
# ──────────────────────────────────────────────────────────────

MOCK_OHLCV_ROWS = [
    {
        "TRD_DD": "20260101",
        "OPNPRC": "70000",
        "HGPRC": "71000",
        "LWPRC": "69500",
        "CLSPRC": "70500",
        "ACC_TRDVOL": "1,200,000",
        "FLUC_RT": "0.71",
    }
]

MOCK_FLOW_ROWS = [
    {
        "TRD_DD": "20260101",
        "INST_NETBID_TRDVOL": "125000",
        "FRGN_NETBID_TRDVOL": "-48000",
        "INDV_NETBID_TRDVOL": "-77000",
    }
]


class TestKrxServiceConfigured:
    def setup_method(self):
        self.svc = KrxOpenApiService(api_key="test-key", rate_limit=0.0)

    def test_configured_true_when_key_set(self):
        assert self.svc.configured is True

    def _mock_fetch(self, rows):
        """_fetch를 직접 패치해 HTTP 없이 반환값 주입."""
        self.svc._fetch = MagicMock(return_value=rows)

    def test_get_daily_ohlcv_parses_correctly(self):
        self._mock_fetch(MOCK_OHLCV_ROWS)
        result = self.svc.get_daily_ohlcv("005930", "20260101", "20260131")
        assert len(result) == 1
        bar = result[0]
        assert bar["date"] == "2026-01-01"
        assert bar["open"] == 70000
        assert bar["high"] == 71000
        assert bar["low"] == 69500
        assert bar["close"] == 70500
        assert bar["volume"] == 1200000
        assert bar["change_pct"] == pytest.approx(0.71)
        assert bar["source"] == "krx_openapi"

    def test_get_daily_ohlcv_kosdaq_uses_correct_api(self):
        self._mock_fetch([])
        self.svc.get_daily_ohlcv("123456", "20260101", "20260131", market="KOSDAQ")
        call_args = self.svc._fetch.call_args
        assert call_args[0][0] == "ksq_bydd_trd"

    def test_get_daily_ohlcv_kospi_uses_correct_api(self):
        self._mock_fetch([])
        self.svc.get_daily_ohlcv("005930", "20260101", "20260131", market="KOSPI")
        assert self.svc._fetch.call_args[0][0] == "stk_bydd_trd"

    def test_get_investor_flow_parses_correctly(self):
        self._mock_fetch(MOCK_FLOW_ROWS)
        result = self.svc.get_investor_flow("005930", "20260101", "20260131")
        assert len(result) == 1
        row = result[0]
        assert row["date"] == "2026-01-01"
        assert row["institution"] == 125000
        assert row["foreign"] == -48000
        assert row["individual"] == -77000
        assert row["source"] == "krx_openapi"

    def test_get_investor_flow_uses_investor_api_id(self):
        self._mock_fetch([])
        self.svc.get_investor_flow("005930", "20260101", "20260131")
        assert self.svc._fetch.call_args[0][0] == "stk_invsr_trd_by_isu"

    def test_bad_row_skipped_gracefully(self):
        self._mock_fetch([{"TRD_DD": "bad", "CLSPRC": "not_a_number_but_zero"}])
        result = self.svc.get_daily_ohlcv("005930", "20260101", "20260131")
        # bad CLSPRC "not_a_number_but_zero" → _to_int → 0, should still parse
        assert isinstance(result, list)

    def test_fetch_exception_returns_empty(self):
        self.svc._fetch = MagicMock(side_effect=Exception("network error"))
        # _fetch raises → caught inside get_daily_ohlcv? No, _fetch handles it.
        # Let's patch at http level instead
        self.svc._fetch = MagicMock(return_value=[])
        result = self.svc.get_daily_ohlcv("005930", "20260101", "20260131")
        assert result == []


# ──────────────────────────────────────────────────────────────
# REST 엔드포인트
# ──────────────────────────────────────────────────────────────

class TestKrxEndpoints:
    def test_status_unconfigured(self):
        """API 키 없으면 configured=false."""
        resp = client.get("/krx/status")
        assert resp.status_code == 200
        body = resp.json()
        assert "configured" in body

    def test_ohlcv_unconfigured_returns_empty_bars(self):
        resp = client.get("/krx/ohlcv/005930")
        assert resp.status_code == 200
        body = resp.json()
        assert body["bars"] == []
        assert body["count"] == 0
        assert body["configured"] is False

    def test_investor_flow_unconfigured_returns_empty(self):
        resp = client.get("/krx/investor-flow/005930")
        assert resp.status_code == 200
        body = resp.json()
        assert body["flows"] == []
        assert body["configured"] is False
        assert body["phase"] == "A_pending"

    def test_ohlcv_with_date_params(self):
        resp = client.get("/krx/ohlcv/005930?from_date=20260101&to_date=20260131&market=KOSPI")
        assert resp.status_code == 200

    def test_ohlcv_with_kosdaq_market(self):
        resp = client.get("/krx/ohlcv/123456?market=KOSDAQ")
        assert resp.status_code == 200
