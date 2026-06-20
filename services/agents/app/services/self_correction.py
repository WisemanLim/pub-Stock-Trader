"""F3.3 전략 자가교정 루프 — 에이전트 결정 이력 기반 전략 이탈(drift) 감시·교정.

멀티에이전트 결정을 누적 관찰해 전략 이탈을 판정하고 보수적 교정안을 제안한다.
판정 신호(셋 중 하나라도 → drift):
  1. 시그널 churn — 연속 결정에서 BUY↔SELL 전환이 잦음(전략 불안정).
  2. 신뢰도 저하 — 최근 평균 confidence 가 임계 미만.
  3. 비중 위반 — 후보 비중이 페르소나 상한 초과.
교정: 비중 상한 클램프 + (churn·저신뢰 시) HOLD 강등. 순수 로직 → 결정적·시험 가능.
"""
from collections import deque

# drift 임계 — 페르소나 무관 공통(과민 방지 보수값).
CHURN_THRESHOLD = 0.5      # 시그널 전환율 ≥ 0.5 → 불안정
MIN_CONFIDENCE = 0.45      # 최근 평균 신뢰도 < 0.45 → 저신뢰
WINDOW = 10                # 관찰 윈도우(최근 N 결정)


def flip_rate(signals: list[str]) -> float:
    """방향성 시그널(BUY/SELL) 전환율 — 직전과 반대 방향 비율. HOLD 는 방향 미정으로 제외."""
    directional = [s for s in signals if s in ("BUY", "SELL")]
    if len(directional) < 2:
        return 0.0
    flips = sum(1 for a, b in zip(directional, directional[1:]) if a != b)
    return flips / (len(directional) - 1)


def detect_drift(
    history: list[dict],
    persona_max: float,
    candidate: dict | None = None,
    *,
    churn_threshold: float = CHURN_THRESHOLD,
    min_confidence: float = MIN_CONFIDENCE,
) -> dict:
    """결정 이력(+후보) → drift 판정 리포트.

    history/candidate 항목: {"signal","confidence","weight"}.
    """
    window = history[-WINDOW:]
    signals = [h["signal"] for h in window]
    if candidate:
        signals = signals + [candidate["signal"]]
    confidences = [h["confidence"] for h in window]
    if candidate:
        confidences = confidences + [candidate["confidence"]]

    fr = flip_rate(signals)
    avg_conf = sum(confidences) / len(confidences) if confidences else 1.0
    weight_breach = bool(candidate and candidate.get("weight", 0.0) > persona_max + 1e-9)

    reasons = []
    if fr >= churn_threshold:
        reasons.append(f"signal_churn(flip_rate={round(fr, 3)}≥{churn_threshold})")
    if avg_conf < min_confidence:
        reasons.append(f"low_confidence(avg={round(avg_conf, 3)}<{min_confidence})")
    if weight_breach:
        reasons.append(f"weight_breach(weight={candidate['weight']}>max={persona_max})")

    return {
        "drift": bool(reasons),
        "reasons": reasons,
        "flip_rate": round(fr, 4),
        "avg_confidence": round(avg_conf, 4),
        "weight_breach": weight_breach,
    }


def correct_decision(candidate: dict, drift: dict, persona_max: float) -> dict:
    """drift 판정에 따른 교정 결정 — 비중 상한 클램프 + 불안정 시 HOLD 강등."""
    signal = candidate["signal"]
    weight = candidate.get("weight", 0.0)
    confidence = candidate.get("confidence", 0.0)
    corrections: list[str] = []

    # 비중 상한 초과 → 클램프(전자금융 무권한·과대포지션 방지).
    if weight > persona_max + 1e-9:
        weight = persona_max
        corrections.append(f"weight_clamped_to_{persona_max}")

    # churn·저신뢰 → 보수적 HOLD 강등(전략 재정렬까지 신규 진입 보류).
    unstable = any(r.startswith(("signal_churn", "low_confidence")) for r in drift["reasons"])
    if unstable and signal != "HOLD":
        signal = "HOLD"
        weight = 0.0
        corrections.append("downgraded_to_HOLD")

    return {
        "signal": signal,
        "weight": round(weight, 3),
        "confidence": confidence,
        "corrected": bool(corrections),
        "corrections": corrections,
    }


class StrategyMonitor:
    """전략 이탈 감시기 — 페르소나별 결정 이력을 누적 관찰하고 후보를 교정.

    in-memory(프로세스 수명). 결정적: 동일 입력열 → 동일 판정.
    """

    def __init__(self, persona_max: float, window: int = WINDOW) -> None:
        self.persona_max = persona_max
        self._history: deque[dict] = deque(maxlen=window)

    def record(self, decision: dict) -> None:
        self._history.append({
            "signal": decision["signal"],
            "confidence": decision.get("confidence", 0.0),
            "weight": decision.get("weight", 0.0),
        })

    def history(self) -> list[dict]:
        return list(self._history)

    def evaluate(self, candidate: dict) -> dict:
        """현재 이력 + 후보로 drift 판정."""
        return detect_drift(self.history(), self.persona_max, candidate)

    def correct(self, candidate: dict) -> tuple[dict, dict]:
        """후보 평가 → (drift, corrected). 교정 결과를 이력에 기록(자가교정 루프 폐환)."""
        drift = self.evaluate(candidate)
        corrected = correct_decision(candidate, drift, self.persona_max)
        self.record(corrected)
        return drift, corrected
