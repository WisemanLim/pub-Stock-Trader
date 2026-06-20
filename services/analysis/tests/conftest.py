"""pytest fixtures — FinanceDataReader mock (네트워크 불필요)."""
import os

# torch 학습을 인프로세스(메인 스레드)로 — mock_fdr 주입·결정성 유지 + macOS OpenMP segfault 회피.
# 프로덕션 기본은 별도 프로세스 오프로드(app/core/offload.py).
os.environ.setdefault("ANALYSIS_INPROC_TRAIN", "1")

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch


# 60거래일 OHLCV — 우상향 추세 + 노이즈 (지표 계산 충분)
_DATES = pd.date_range("2024-01-02", periods=60, freq="B")
_base = np.linspace(70000, 75000, 60)
_noise = np.sin(np.arange(60) / 3) * 800
_close = _base + _noise
SAMPLE_DF = pd.DataFrame(
    {
        "Open": _close - 200,
        "High": _close + 400,
        "Low": _close - 400,
        "Close": _close,
        "Volume": np.linspace(1_000_000, 1_500_000, 60).astype(int),
        "Change": np.r_[0.0, np.diff(_close) / _close[:-1]],
    },
    index=_DATES,
)

LISTING_DF = pd.DataFrame({
    "Code": ["005930", "000660", "035720"],
    "Name": ["삼성전자", "SK하이닉스", "카카오"],
    "Market": ["KOSPI", "KOSPI", "KOSPI"],
})


@pytest.fixture
def mock_fdr():
    with patch("FinanceDataReader.DataReader", return_value=SAMPLE_DF):
        yield


@pytest.fixture
def mock_fdr_empty():
    with patch("FinanceDataReader.DataReader", return_value=pd.DataFrame()):
        yield


@pytest.fixture
def mock_listing():
    with patch("FinanceDataReader.StockListing", return_value=LISTING_DF), \
         patch("FinanceDataReader.DataReader", return_value=SAMPLE_DF):
        yield


@pytest.fixture
def client():
    # lifespan 핸들러 없음 → 컨텍스트매니저(포털 스레드) 회피.
    # torch/OpenMP 환경에서 anyio blocking-portal 스레드 join 시 segfault 방지.
    from app.main import app
    return TestClient(app)
