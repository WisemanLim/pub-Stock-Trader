"""F3.1 멀티에이전트 스키마."""
from pydantic import BaseModel


class AnalyzeRequest(BaseModel):
    ticker: str
    persona: str = "swing"  # scalper | day | swing | position


class AgentNote(BaseModel):
    agent: str
    summary: str
    data: dict = {}


class Decision(BaseModel):
    signal: str          # BUY | SELL | HOLD
    weight: float        # 0.0 ~ 1.0 포지션 비중
    confidence: float
    rationale: str


class AnalyzeResponse(BaseModel):
    ticker: str
    persona: str
    notes: list[AgentNote]
    decision: Decision


# ── F3.3 전략 자가교정 ──

class DecisionRecord(BaseModel):
    signal: str          # BUY | SELL | HOLD
    confidence: float = 0.0
    weight: float = 0.0


class SelfCorrectRequest(BaseModel):
    persona: str = "swing"
    history: list[DecisionRecord] = []   # 과거 결정(오래된 → 최신)
    candidate: DecisionRecord            # 이번 결정 후보


class DriftReport(BaseModel):
    drift: bool
    reasons: list[str]
    flip_rate: float
    avg_confidence: float
    weight_breach: bool


class CorrectedDecision(BaseModel):
    signal: str
    weight: float
    confidence: float
    corrected: bool
    corrections: list[str]


class SelfCorrectResponse(BaseModel):
    persona: str
    drift: DriftReport
    original: DecisionRecord
    corrected: CorrectedDecision
