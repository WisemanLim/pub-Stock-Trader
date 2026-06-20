"""rag — Quant RAG 서비스 (F3.2): 금융문서 벡터검색·LLM 환각차단."""
from fastapi import FastAPI

from app.api import rag
from app.core.config import settings

app = FastAPI(
    title=settings.app_name,
    description="F3.2: 금융문서 하이브리드 검색(벡터+키워드) + 근거기반 답변(환각차단) + 평가",
    version="0.1.0",
)

app.include_router(rag.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "rag", "env": settings.env}
