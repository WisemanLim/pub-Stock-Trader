# test/impl/14 — 차수 14 고도화 시험 시나리오

**범위**: ERC 정밀해(Newton) · 분포형 정책 그라디언트 · 종목별 서킷브레이커 · full VAR(1) prewhitening
**차수**: 14
**러너**: pytest(Python) · cargo test(Rust)

## ERC 정밀해 Newton (services/analysis)

| TC | 시나리오 | 기대 |
|----|----------|------|
| EN-01 | erc_newton 합성 | finite |
| EN-02 | 위험기여 균등 | 독립자산 RC 거의 동일 |

## 분포형 정책 그라디언트 (services/analysis)

| TC | 시나리오 | 기대 |
|----|----------|------|
| DP-01 | DPG 구조 | strategy=dpg, n_quantiles=8 |
| DP-02 | 시드 결정성 | 동일 final_equity |
| DP-03 | 데이터 부족 | ValueError |
| DP-04 | strategies 에 dpg | True |

## 종목별 서킷브레이커 (services/ingest)

| TC | 시나리오 | 기대 |
|----|----------|------|
| PT-01 | 종목 실패 → ticker open | 해당 종목 차단, 타 종목 정상, 전역 닫힘 |
| PT-02 | cooldown 후 해제 | 재구독 가능 |

## full VAR(1) prewhitening (core/risk-engine)

| TC | 시나리오 | 기대 |
|----|----------|------|
| FV-01 | full VAR QS HAC | 유한 SE, alpha+betas |

## 금융 규제 케이스 (COMPLIANCE.md)

- **정밀 위험균등**: ERC Newton(Spinu 볼록해) → 수렴 보장 동일 위험기여.
- **분포 인지 정책**: DPG 분포형 critic → 가치 분포 baseline(분산 인지 어드밴티지).
- **장애 격리**: 종목별 서킷브레이커 → 단일 종목 장애가 전체 차단으로 전파 안 됨.
- **최적 HAC**: full VAR(1) prewhitening → 강자기상관 모멘트 정확 백색화.
