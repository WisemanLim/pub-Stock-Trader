"""인메모리 벡터 스토어 — 코사인 + 키워드 하이브리드 검색 (F3.2).

운영 전환: pgvector(pgvector/pgvector:pg17 이미 가동) 로 교체.
  CREATE TABLE docs (id text, content text, meta jsonb, embedding vector(256));
  SELECT ... ORDER BY embedding <=> $query LIMIT k;
현재는 단일 프로세스 인메모리 — Phase 3 에서 psycopg + pgvector 로 영속화.
"""
from app.services.embeddings import cosine, embed


class VectorStore:
    def __init__(self) -> None:
        self._docs: list[dict] = []

    def add(self, doc_id: str, content: str, meta: dict | None = None) -> None:
        self._docs.append({
            "id": doc_id,
            "content": content,
            "meta": meta or {},
            "embedding": embed(content),
            "tokens": set(content.lower().split()),
        })

    def clear(self) -> None:
        self._docs.clear()

    def count(self) -> int:
        return len(self._docs)

    def search(self, query: str, k: int = 3) -> list[dict]:
        if not self._docs:
            return []
        q_emb = embed(query)
        q_tokens = set(query.lower().split())
        scored = []
        for d in self._docs:
            vec_score = cosine(q_emb, d["embedding"])
            overlap = len(q_tokens & d["tokens"])
            kw_score = overlap / len(q_tokens) if q_tokens else 0.0
            score = 0.7 * vec_score + 0.3 * kw_score  # 하이브리드
            scored.append((score, d))
        scored.sort(key=lambda x: x[0], reverse=True)
        results = []
        for score, d in scored[:k]:
            results.append({
                "id": d["id"],
                "content": d["content"],
                "meta": d["meta"],
                "score": round(float(score), 4),
            })
        return results


def _make_store():
    """DATABASE_URL 이 postgres 면 pgvector 영속화, 아니면 인메모리.

    pgvector 연결 실패 시 인메모리로 안전 폴백(부분 장애 격리).
    """
    from app.core.config import settings

    dsn = settings.database_url
    if dsn.startswith("postgresql://") or dsn.startswith("postgres://"):
        try:
            from app.services.pgvector_store import PgVectorStore
            pg = PgVectorStore(dsn)
            pg.count()  # 연결·스키마 확인
            return pg
        except Exception:
            return VectorStore()
    return VectorStore()


store = _make_store()
