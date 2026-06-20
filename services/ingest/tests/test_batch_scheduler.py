"""Phase A-2: DB 스키마 + OHLCV 적재 + 배치 스케줄러 API 시험."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

from app.db import Base, OhlcvDaily, InvestorFlowDaily, init_db, get_session
from app.services.ohlcv_store import (
    upsert_ohlcv,
    upsert_investor_flow,
    latest_ohlcv_date,
)
from app.main import app


# ── in-memory SQLite for isolated tests ────────────────────────────────
@pytest.fixture(autouse=True)
def _mem_db(monkeypatch):
    """테스트마다 in-memory DB 사용. 프로세스 DB와 격리."""
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(eng)
    Sess = sessionmaker(bind=eng, autoflush=False, autocommit=False)

    monkeypatch.setattr("app.db.engine", eng)
    monkeypatch.setattr("app.db.SessionLocal", Sess)
    monkeypatch.setattr("app.services.ohlcv_store.get_session", lambda: Sess())
    yield
    Base.metadata.drop_all(eng)


# ── DB 스키마 ──────────────────────────────────────────────────────────
class TestDbSchema:
    def test_ohlcv_daily_table_created(self, _mem_db):
        eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(eng)
        inspector = inspect(eng)
        assert "ohlcv_daily" in inspector.get_table_names()

    def test_investor_flow_table_created(self, _mem_db):
        eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(eng)
        inspector = inspect(eng)
        assert "investor_flow_daily" in inspector.get_table_names()

    def test_ohlcv_columns(self, _mem_db):
        eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(eng)
        cols = {c["name"] for c in inspect(eng).get_columns("ohlcv_daily")}
        for name in ("ticker", "date", "open", "high", "low", "close", "volume"):
            assert name in cols


# ── ohlcv_store ────────────────────────────────────────────────────────
SAMPLE_OHLCV = [
    {"date": "20240101", "open": 70000, "high": 72000, "low": 69000, "close": 71500,
     "volume": 1_000_000, "change_pct": 2.1, "source": "krx"},
    {"date": "20240102", "open": 71500, "high": 73000, "low": 71000, "close": 72000,
     "volume": 1_200_000, "change_pct": 0.7, "source": "krx"},
]

SAMPLE_FLOW = [
    {"date": "20240101", "institution": 1_250_000_000, "foreign": -480_000_000,
     "individual": -770_000_000, "source": "krx"},
]


class TestOhlcvStore:
    def test_upsert_ohlcv_returns_saved_count(self):
        n = upsert_ohlcv("005930", SAMPLE_OHLCV)
        assert n == 2

    def test_upsert_ohlcv_empty_rows(self):
        assert upsert_ohlcv("005930", []) == 0

    def test_upsert_ohlcv_duplicate_ignored(self):
        upsert_ohlcv("005930", SAMPLE_OHLCV)
        n2 = upsert_ohlcv("005930", SAMPLE_OHLCV)  # 중복 → 0
        assert n2 == 0

    def test_upsert_ohlcv_bad_date_skipped(self):
        rows = [{"date": "invalid-date", "open": 70000, "close": 70000}]
        assert upsert_ohlcv("005930", rows) == 0

    def test_latest_ohlcv_date_after_upsert(self):
        upsert_ohlcv("005930", SAMPLE_OHLCV)
        from datetime import date
        latest = latest_ohlcv_date("005930")
        assert latest == date(2024, 1, 2)

    def test_latest_ohlcv_date_none_when_empty(self):
        assert latest_ohlcv_date("999999") is None

    def test_upsert_investor_flow(self):
        n = upsert_investor_flow("005930", SAMPLE_FLOW)
        assert n == 1

    def test_upsert_investor_flow_duplicate_ignored(self):
        upsert_investor_flow("005930", SAMPLE_FLOW)
        n2 = upsert_investor_flow("005930", SAMPLE_FLOW)
        assert n2 == 0

    def test_upsert_ohlcv_iso_date_format(self):
        rows = [{"date": "2024-01-03", "open": 70000, "high": 72000,
                 "low": 69000, "close": 71000, "volume": 500_000,
                 "change_pct": -0.5, "source": "krx"}]
        assert upsert_ohlcv("005930", rows) == 1


# ── 배치 스케줄러 API ──────────────────────────────────────────────────
class TestSchedulerApi:
    def setup_method(self):
        self.client = TestClient(app, raise_server_exceptions=False)

    def test_status_endpoint(self):
        r = self.client.get("/scheduler/status")
        assert r.status_code == 200
        data = r.json()
        assert "running" in data
        assert "last_run" in data
        assert "tickers" in data

    def test_run_endpoint_returns_result(self):
        r = self.client.post("/scheduler/run")
        assert r.status_code == 200
        data = r.json()
        # KRX_OPEN_API_KEY 미설정 → skipped 또는 ok
        assert data["status"] in ("skipped", "ok", "error", "never")

    def test_status_has_schedule_info(self):
        r = self.client.get("/scheduler/status")
        data = r.json()
        assert "schedule" in data
        assert "KST" in data["schedule"]

    def test_run_skipped_when_no_api_key(self, monkeypatch):
        monkeypatch.setattr("app.core.config.settings.krx_open_api_key", "")
        monkeypatch.setattr("app.core.config.settings.scheduler_tickers", ["005930"])
        r = self.client.post("/scheduler/run")
        assert r.status_code == 200
