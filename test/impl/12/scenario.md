# test/impl/12 — 차수 12 고도화 시험 시나리오

**범위**: 리스크패리티·CCIPCA · CVaR/FQF · ack 타임아웃 재송신 · Andrews 자동 대역폭 NW
**차수**: 12
**러너**: pytest(Python) · cargo test(Rust)

## 리스크패리티·CCIPCA (services/analysis)

| TC | 시나리오 | 기대 |
|----|----------|------|
| RP-01 | riskparity 합성 | finite, 안정 비중↑ |
| RP-02 | ccipca 합성 | 증분 주성분 z-score |
| RP-03 | 리스크패리티 가중합=1 | Σw=1, 안정>변동 |

## CVaR/FQF (services/analysis)

| TC | 시나리오 | 기대 |
|----|----------|------|
| CV-01 | CVaR risk-sensitive | cvar_alpha 반영, 하위분위수 행동가치 |
| FQ-01 | FQF 구조 | strategy=fqf, 분위수 비율 학습 |
| FQ-02 | FQF 시드 결정성 | 동일 final_equity |
| FQ-03 | strategies 에 fqf | True |

## ack 타임아웃 재송신 (services/ingest)

| TC | 시나리오 | 기대 |
|----|----------|------|
| TO-01 | 타임아웃 전/후 | 전 무재송신, 후 재송신 |
| TO-02 | max_resend 초과 | failed 표시 |
| TO-03 | ack 수신 후 정지 | 재송신 없음 |

## Andrews 자동 대역폭 NW (core/risk-engine)

| TC | 시나리오 | 기대 |
|----|----------|------|
| AB-01 | 자동 대역폭 회귀 | alpha+betas+se+lag, lag<n |
| AB-02 | andrews_bandwidth | 잡음 작은 lag, 짧으면 0 |

## 금융 규제 케이스 (COMPLIANCE.md)

- **리스크 균형**: 리스크패리티 가중 → 단일 지표 위험 집중 방지(분산).
- **꼬리위험 정책**: CVaR risk-sensitive 행동 → 하방 위험 회피 매매(보수적).
- **세션 복원력**: ack 타임아웃 재송신·실패 감지 → 구독 신뢰성.
- **통계 엄밀성**: Andrews 데이터기반 대역폭 → 임의 lag 선택 편의 제거(객관적 HAC).
