"""pgvector 영속 벡터 스토어 (F3.2 Phase 3).

DATABASE_URL 이 postgresql 일 때 활성. 인메모리와 동일 인터페이스
(add/clear/count/search) → vector_store.store 가 설정에 따라 선택.

스키마:
  CREATE TABLE rag_docs (
    id text PRIMARY KEY, content text, meta jsonb, embedding vector(256)
  );
검색: 코사인 거리(<=>) 상위 k → 키워드 오버랩 하이브리드 재랭킹.
"""
from app.services.embeddings import DIM, embed


class PgVectorStore:
    def __init__(self, dsn: str) -> None:
        # psycopg DSN 형식으로 변환 (sqlalchemy 형식 postgresql:// 도 호환).
        self._dsn = dsn
        self._ready = False

    def _conn(self):
        import psycopg
        from pgvector.psycopg import register_vector

        conn = psycopg.connect(self._dsn)
        register_vector(conn)
        return conn

    def _ensure(self) -> None:
        if self._ready:
            return
        with self._conn() as conn:
            conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
            conn.execute(
                f"""
                CREATE TABLE IF NOT EXISTS rag_docs (
                    id text PRIMARY KEY,
                    content text NOT NULL,
                    meta jsonb DEFAULT '{{}}'::jsonb,
                    embedding vector({DIM})
                )
                """
            )
            conn.commit()
        self._ready = True

    def add(self, doc_id: str, content: str, meta: dict | None = None) -> None:
        import json
        from pgvector import Vector
        self._ensure()
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO rag_docs (id, content, meta, embedding)
                VALUES (%s, %s, %s::jsonb, %s)
                ON CONFLICT (id) DO UPDATE
                SET content = EXCLUDED.content, meta = EXCLUDED.meta, embedding = EXCLUDED.embedding
                """,
                (doc_id, content, json.dumps(meta or {}), Vector(embed(content))),
            )
            conn.commit()

    def clear(self) -> None:
        self._ensure()
        with self._conn() as conn:
            conn.execute("TRUNCATE rag_docs")
            conn.commit()

    def count(self) -> int:
        self._ensure()
        with self._conn() as conn:
            row = conn.execute("SELECT count(*) FROM rag_docs").fetchone()
            return int(row[0]) if row else 0

    def search(self, query: str, k: int = 3) -> list[dict]:
        from pgvector import Vector
        self._ensure()
        q_emb = Vector(embed(query))
        q_tokens = set(query.lower().split())
        # 벡터 후보를 넉넉히(k*3) 뽑아 키워드 하이브리드 재랭킹.
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT id, content, meta, 1 - (embedding <=> %s) AS vec_score
                FROM rag_docs
                ORDER BY embedding <=> %s
                LIMIT %s
                """,
                (q_emb, q_emb, k * 3),
            ).fetchall()

        scored = []
        for doc_id, content, meta, vec_score in rows:
            overlap = len(q_tokens & set(content.lower().split()))
            kw_score = overlap / len(q_tokens) if q_tokens else 0.0
            score = 0.7 * float(vec_score) + 0.3 * kw_score
            scored.append((score, doc_id, content, meta))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [
            {"id": d, "content": c, "meta": m or {}, "score": round(s, 4)}
            for s, d, c, m in scored[:k]
        ]
