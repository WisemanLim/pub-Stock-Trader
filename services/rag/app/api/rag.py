"""F3.2 Quant RAG API — 인덱싱·검색·평가."""
from fastapi import APIRouter

from app.schemas.rag import (
    EvalRequest,
    EvalResponse,
    IngestRequest,
    IngestResponse,
    QueryRequest,
    QueryResponse,
    RetrievedDoc,
)
from app.services.answerer import answer
from app.services.vector_store import store

router = APIRouter(prefix="/rag", tags=["rag"])


@router.post("/ingest", response_model=IngestResponse)
def ingest(req: IngestRequest) -> IngestResponse:
    """공시·매크로 보고서 등 문서를 벡터스토어에 인덱싱."""
    for doc in req.documents:
        store.add(doc.id, doc.content, doc.meta)
    return IngestResponse(ingested=len(req.documents), total=store.count())


@router.post("/query", response_model=QueryResponse)
def query(req: QueryRequest) -> QueryResponse:
    """하이브리드 검색 + 근거 기반 답변 (환각 차단)."""
    sources = store.search(req.query, k=req.k)
    text, grounded = answer(req.query, sources)
    return QueryResponse(
        query=req.query,
        answer=text,
        sources=[RetrievedDoc(**s) for s in sources],
        grounded=grounded,
    )


@router.post("/ir-report")
def ingest_ir_report(ticker: str, title: str = "", content: str = "") -> dict:
    """D-2: 한국IR협의회 AI 분석보고서 RAG 적재.

    ticker + 보고서 텍스트를 벡터스토어에 인덱싱.
    doc_id = ir:{ticker}:{timestamp_prefix}
    """
    import time
    if not content.strip():
        return {"status": "error", "message": "content 필수"}
    doc_id = f"ir:{ticker.upper()}:{int(time.time())}"
    store.add(doc_id, content, {"ticker": ticker.upper(), "title": title, "type": "ir_report"})
    return {"status": "ok", "doc_id": doc_id, "total": store.count()}


@router.get("/ir-report/{ticker}")
def query_ir_report(ticker: str, k: int = 3) -> dict:
    """D-2: 종목별 IR 분석보고서 검색 및 AI 요약."""
    query = f"{ticker.upper()} 기업 분석 투자의견 목표주가"
    sources = store.search(query, k=k)
    # 해당 ticker 문서 우선 필터
    ticker_sources = [s for s in sources if s.get("meta", {}).get("ticker") == ticker.upper()]
    if not ticker_sources:
        return {
            "ticker": ticker.upper(),
            "available": False,
            "answer": "IR 보고서 미적재. POST /rag/ir-report 로 보고서를 먼저 적재하세요.",
            "sources": [],
        }
    text, grounded = answer(query, ticker_sources)
    return {
        "ticker": ticker.upper(),
        "available": True,
        "answer": text,
        "grounded": grounded,
        "sources": [{"id": s["id"], "title": s.get("meta", {}).get("title", ""), "score": s.get("score", 0)} for s in ticker_sources],
    }


@router.post("/eval", response_model=EvalResponse)
def evaluate(req: EvalRequest) -> EvalResponse:
    """Ragas 유사 평가 — groundedness·context_recall (경량 구현)."""
    sources = store.search(req.query, k=req.k)
    ctx = " ".join(s["content"].lower() for s in sources)
    ans_tokens = [t for t in req.answer.lower().split() if len(t) > 2]
    grounded = (
        sum(1 for t in ans_tokens if t in ctx) / len(ans_tokens)
        if ans_tokens else 0.0
    )
    q_tokens = [t for t in req.query.lower().split() if len(t) > 2]
    recall = (
        sum(1 for t in q_tokens if t in ctx) / len(q_tokens)
        if q_tokens else 0.0
    )
    return EvalResponse(
        query=req.query,
        groundedness=round(grounded, 4),
        context_recall=round(recall, 4),
        sources_used=len(sources),
    )
