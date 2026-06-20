# test/impl/15 — 차수 15 고도화 시험 시나리오

**범위**: Ledoit-Wolf 축소 · PPO/A2C·GAE · 채널별 서킷브레이커 · VAR 차수선택(AIC)
**차수**: 15
**러너**: pytest(Python) · cargo test(Rust)

## Ledoit-Wolf 축소 (services/analysis)

| TC | 시나리오 | 기대 |
|----|----------|------|
| LW-01 | 축소 공분산 PSD | 고유값 ≥0 |
| LW-02 | erc_lw 합성 | finite |

## PPO/A2C·GAE (services/analysis)

| TC | 시나리오 | 기대 |
|----|----------|------|
| PA-01 | A2C(GAE) | mode=a2c |
| PA-02 | PPO clip | mode=ppo |
| PA-03 | PPO 시드 결정성 | 동일 final_equity |

## 채널별 서킷브레이커 (services/ingest)

| TC | 시나리오 | 기대 |
|----|----------|------|
| CH-01 | 채널 실패 → 채널 open | 채널 차단, 타 채널 정상 |
| CH-02 | cooldown 해제 | 자동 복구 |

## VAR 차수선택 AIC (core/risk-engine)

| TC | 시나리오 | 기대 |
|----|----------|------|
| AI-01 | AIC 차수선택 회귀 | alpha+betas+se+p≤max |
| AI-02 | AR 차수 AIC | 강자기상관 p≥1 |

## 금융 규제 케이스 (COMPLIANCE.md)

- **소표본 안정**: Ledoit-Wolf 축소 → 공분산 추정 오차 완화(고유값 압축).
- **안정 정책학습**: PPO clip → 정책 갱신 폭 제한(과적합·발산 방지).
- **장애 격리 다계층**: 채널별 서킷브레이커 → 소스 단위 장애 격리(종목·전역과 독립).
- **객관적 모형선택**: AIC VAR 차수 → 데이터기반 백색화 차수(과소/과대 방지).
