"""F3.2 pgvector 영속화 통합 시험 — 실 postgres 필요 (없으면 skip).

실행 전제: `make up` 으로 postgres(pgvector:pg17) 기동.
DSN 미연결 시 자동 skip → CI/오프라인 안전.
"""
import pytest

DSN = "postgresql://app:app@localhost:5432/stock_trader"


def _pg_available() -> bool:
    try:
        import psycopg
        with psycopg.connect(DSN, connect_timeout=2):
            return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _pg_available(), reason="postgres 미연결")


@pytest.fixture
def pg_store():
    from app.services.pgvector_store import PgVectorStore
    s = PgVectorStore(DSN)
    s.clear()
    yield s
    s.clear()


def test_pgvector_add_and_count(pg_store):
    pg_store.add("d1", "Federal Reserve held interest rates steady", {"type": "macro"})
    pg_store.add("d2", "KOSPI semiconductor rally on chip demand", {"type": "equity"})
    assert pg_store.count() == 2


def test_pgvector_upsert(pg_store):
    pg_store.add("d1", "original content", {})
    pg_store.add("d1", "updated content", {})
    assert pg_store.count() == 1  # 동일 id → upsert


def test_pgvector_search_ranks_relevant(pg_store):
    pg_store.add("fed", "Federal Reserve held interest rates steady at 5.5 percent", {})
    pg_store.add("kospi", "KOSPI semiconductor sector rallied on memory chip demand", {})
    pg_store.add("boj", "Bank of Japan maintained negative interest rate policy", {})
    results = pg_store.search("federal reserve interest rates", k=2)
    assert len(results) <= 2
    assert results[0]["id"] == "fed"
    assert "score" in results[0]


def test_pgvector_persists_across_instances(pg_store):
    pg_store.add("persist1", "macro economic report on inflation", {})
    from app.services.pgvector_store import PgVectorStore
    other = PgVectorStore(DSN)  # 새 인스턴스 = 새 연결
    assert other.count() >= 1  # 영속화 확인
