"""pytest fixtures — RAG 서비스."""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from app.main import app
    from app.services.vector_store import store
    store.clear()  # 테스트 격리
    with TestClient(app) as c:
        yield c


DOCS = [
    {
        "id": "fed-2024-01",
        "content": "Federal Reserve held interest rates steady at 5.5 percent in January 2024 citing persistent inflation.",
        "meta": {"type": "macro", "source": "fed"},
    },
    {
        "id": "kospi-note",
        "content": "KOSPI semiconductor sector rallied on strong memory chip demand and export growth.",
        "meta": {"type": "equity", "source": "analyst"},
    },
    {
        "id": "boj-policy",
        "content": "Bank of Japan maintained negative interest rate policy and yield curve control.",
        "meta": {"type": "macro", "source": "boj"},
    },
]
