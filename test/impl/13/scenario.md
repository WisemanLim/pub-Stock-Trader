# test/impl/13 — 차수 13 고도화 시험 시나리오

**범위**: 공분산 ERC·상태의존 FQF · 지수 백오프 재송신·서킷브레이커 · VAR prewhitening·QS 커널
**차수**: 13
**러너**: pytest(Python) · cargo test(Rust)

## 공분산 ERC (services/analysis)

| TC | 시나리오 | 기대 |
|----|----------|------|
| ER-01 | erc 합성 | finite |
| ER-02 | ERC 가중합=1 | Σw=1, w>0 |

## 상태의존 FQF (services/analysis)

| TC | 시나리오 | 기대 |
|----|----------|------|
| SF-01 | 상태의존 FQF 구조 | fqf_state_dependent=True |
| SF-02 | 시드 결정성 | 동일 final_equity |

## 지수 백오프 재송신·서킷브레이커 (services/ingest)

| TC | 시나리오 | 기대 |
|----|----------|------|
| BO-01 | 지수 백오프 간격 | 5·2^n 간격 재송신 |
| BO-02 | max 초과 failed | failed 표시 |
| CB-01 | 서킷 open + 차단 | 연속실패 threshold → 신규 구독 차단 |
| CB-02 | cooldown 후 half_open | 차단 해제 |

## VAR prewhitening·QS 커널 (core/risk-engine)

| TC | 시나리오 | 기대 |
|----|----------|------|
| QS-01 | QS HAC prewhiten on/off | 유한 SE, alpha+betas |
| QS-02 | QS 커널 가중 성질 | w(0)=1, 먼 시차 감쇠 |

## 금융 규제 케이스 (COMPLIANCE.md)

- **위험기여 균등**: 공분산 ERC → 상관 고려 동일 위험기여(엄밀 분산).
- **적응 분위수**: 상태의존 FQF → 시장상태별 분위수 비율 학습.
- **세션 보호**: 지수 백오프 + 서킷브레이커 → 장애 전파 차단(폭주 방지).
- **통계 엄밀**: QS 커널(비절단) + VAR prewhitening → 최적 HAC 분산추정.
