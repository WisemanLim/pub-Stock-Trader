"""F3.2 Quant RAG 시험 — ingest·query·eval + 환각차단."""
from tests.conftest import DOCS


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["service"] == "rag"


def test_ingest(client):
    r = client.post("/rag/ingest", json={"documents": DOCS})
    assert r.status_code == 200
    data = r.json()
    assert data["ingested"] == 3
    assert data["total"] == 3


def test_query_returns_relevant_source(client):
    client.post("/rag/ingest", json={"documents": DOCS})
    r = client.post("/rag/query", json={"query": "federal reserve interest rates", "k": 2})
    assert r.status_code == 200
    data = r.json()
    assert len(data["sources"]) <= 2
    # 가장 관련된 문서가 Fed 문서여야
    assert data["sources"][0]["id"] == "fed-2024-01"
    assert data["grounded"] is True


def test_query_empty_store_blocks_hallucination(client):
    """근거 문서 없으면 환각 차단 — grounded=False."""
    r = client.post("/rag/query", json={"query": "tesla stock price", "k": 3})
    assert r.status_code == 200
    data = r.json()
    assert data["sources"] == []
    assert data["grounded"] is False
    assert "근거" in data["answer"]


def test_eval_groundedness(client):
    client.post("/rag/ingest", json={"documents": DOCS})
    r = client.post("/rag/eval", json={
        "query": "federal reserve rates",
        "answer": "Federal Reserve held interest rates steady at 5.5 percent",
        "k": 2,
    })
    assert r.status_code == 200
    data = r.json()
    assert data["groundedness"] > 0.5
    assert data["sources_used"] >= 1


def test_openapi_routes(client):
    paths = client.get("/openapi.json").json()["paths"]
    assert "/rag/ingest" in paths
    assert "/rag/query" in paths
    assert "/rag/eval" in paths
