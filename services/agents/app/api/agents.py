"""F3.1 멀티에이전트 API + F3.3 전략 자가교정."""
from fastapi import APIRouter, HTTPException

from app.schemas.agents import (
    AgentNote,
    AnalyzeRequest,
    AnalyzeResponse,
    CorrectedDecision,
    Decision,
    DriftReport,
    SelfCorrectRequest,
    SelfCorrectResponse,
)
from app.services.orchestrator import PERSONA_MAX_WEIGHT, run_pipeline
from app.services.self_correction import correct_decision, detect_drift

router = APIRouter(prefix="/agents", tags=["agents"])


@router.post("/analyze", response_model=AnalyzeResponse)
def analyze(req: AnalyzeRequest) -> AnalyzeResponse:
    """4-에이전트 협업 분석 → 최종 매매 시그널."""
    if req.persona not in PERSONA_MAX_WEIGHT:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown persona: {req.persona}. Valid: {list(PERSONA_MAX_WEIGHT)}",
        )
    result = run_pipeline(req.ticker.upper(), req.persona)
    return AnalyzeResponse(
        ticker=result["ticker"],
        persona=result["persona"],
        notes=[AgentNote(**n) for n in result["notes"]],
        decision=Decision(**result["decision"]),
    )


@router.get("/personas")
def personas() -> dict:
    """지원 페르소나 + 포지션 비중 상한."""
    return PERSONA_MAX_WEIGHT


@router.post("/self_correct", response_model=SelfCorrectResponse)
def self_correct(req: SelfCorrectRequest) -> SelfCorrectResponse:
    """F3.3 전략 이탈 감시·교정 — 결정 이력+후보로 drift 판정 후 보수적 교정안 반환."""
    if req.persona not in PERSONA_MAX_WEIGHT:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown persona: {req.persona}. Valid: {list(PERSONA_MAX_WEIGHT)}",
        )
    persona_max = PERSONA_MAX_WEIGHT[req.persona]
    history = [h.model_dump() for h in req.history]
    candidate = req.candidate.model_dump()
    drift = detect_drift(history, persona_max, candidate)
    corrected = correct_decision(candidate, drift, persona_max)
    return SelfCorrectResponse(
        persona=req.persona,
        drift=DriftReport(**drift),
        original=req.candidate,
        corrected=CorrectedDecision(**corrected),
    )
