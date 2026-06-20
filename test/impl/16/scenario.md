# test/impl/16 — 차수 16 고도화 시험 시나리오

**범위**: OAS·상수상관 타깃 · minibatch SGD·엔트로피·KL 조기종료 · half-open 탐침 송신 · full VAR(p)·BIC/HQ
**차수**: 16
**러너**: pytest(Python) · cargo test(Rust)

## OAS·상수상관 타깃 (services/analysis)

| TC | 시나리오 | 기대 |
|----|----------|------|
| OA-01 | 상수상관 타깃 | 대각 보존·대칭 |
| OA-02 | OAS 축소 PSD | 고유값≥0 |
| OA-03 | erc_cc·erc_oas 합성 | finite |

## PPO 강화 (services/analysis)

| TC | 시나리오 | 기대 |
|----|----------|------|
| PP-01 | minibatch SGD | mb 학습 동작 |
| PP-02 | 엔트로피 보너스 | entropy_coef 반영 |
| PP-03 | KL 조기종료 | kl_target 초과 시 epoch 중단 |
| PP-04 | 시드 결정성 | 동일 final_equity |

## half-open 탐침 송신 (services/ingest)

| TC | 시나리오 | 기대 |
|----|----------|------|
| HP-01 | half_open 탐침 성공 | closed 전환 |
| HP-02 | 탐침 실패 | 재오픈 |

## full VAR(p)·BIC/HQ (core/risk-engine)

| TC | 시나리오 | 기대 |
|----|----------|------|
| VR-01 | VAR(p) aic/bic/hq | alpha+betas+se+p≤max |
| VR-02 | det 헬퍼 | I=1, 대각=곱 |

## 금융 규제 케이스 (COMPLIANCE.md)

- **타깃 선택**: OAS(자동 δ)·상수상관 → 자산 상관구조 반영 안정 공분산.
- **정책 안정성**: KL 조기종료 + 엔트로피 → 과도 갱신·조기수렴 방지.
- **무중단 복구**: half-open 탐침 → 점진 복구(전체 재개 전 단일 검증).
- **모형 절약**: BIC/HQ → AIC 대비 보수적 차수(과적합 억제).
