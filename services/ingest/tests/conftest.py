"""pytest fixtures — FinanceDataReader 를 mock 으로 대체 (네트워크 불필요)."""
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch


SAMPLE_DATES = pd.date_range("2024-01-02", periods=5, freq="B")
SAMPLE_DF = pd.DataFrame(
    {
        "Open":   [70000.0, 71000.0, 72000.0, 71500.0, 73000.0],
        "High":   [71000.0, 72000.0, 73000.0, 72500.0, 74000.0],
        "Low":    [69500.0, 70500.0, 71500.0, 71000.0, 72500.0],
        "Close":  [70500.0, 71500.0, 72500.0, 72000.0, 73500.0],
        "Volume": [1_000_000, 1_100_000, 950_000, 1_050_000, 1_200_000],
        "Change": [0.005, 0.014, 0.014, -0.007, 0.021],
    },
    index=SAMPLE_DATES,
)


@pytest.fixture
def mock_fdr():
    with patch("app.services.finance_reader.fdr.DataReader", return_value=SAMPLE_DF) as m:
        yield m


@pytest.fixture
def mock_fdr_empty():
    with patch("app.services.finance_reader.fdr.DataReader", return_value=pd.DataFrame()) as m:
        yield m


@pytest.fixture
def client():
    from app.main import app
    with TestClient(app) as c:
        yield c
