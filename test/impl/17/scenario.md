# test/impl/17 — 차수 17 고도화 시험 시나리오

**범위**: 비선형 축소(NLW) · 병렬 롤아웃·LR 스케줄 · 점진 트래픽 증대(rate ramp) · VAR 안정성 사영·Yule-Walker
**차수**: 17
**러너**: pytest(Python) · cargo test(Rust)

## 비선형 축소 NLW (services/analysis)

| TC | 시나리오 | 기대 |
|----|----------|------|
| NL-01 | NLW 축소 PSD·고유값 분산↓ | PSD, std 감소 |
| NL-02 | erc_nlw 합성 | finite |

## 점진 트래픽 증대 (services/ingest)

| TC | 시나리오 | 기대 |
|----|----------|------|
| RR-01 | ramp 점진 허용 | 한도 내 허용·초과 차단·tick 후 상향 |
| RR-02 | ramp 비활성 전체 허용 | True |

## VAR 안정성 사영·Yule-Walker (core/risk-engine)

| TC | 시나리오 | 기대 |
|----|----------|------|
| ST-01 | qs_var stabilize | 유한 SE |
| ST-02 | spectral_radius·stabilize_scale | 반경 산출·축소 |
| ST-03 | Yule-Walker AR(1) | φ₁ 양의 지속성 |

## 병렬 롤아웃·LR 스케줄 (services/analysis)

| TC | 시나리오 | 기대 |
|----|----------|------|
| PR-01 | 병렬 롤아웃(n_rollouts) | 다중 에피소드 평균 그라디언트 |
| PR-02 | LR 선형 감쇠 | lr_final 적용 |
| PR-03 | 시드 결정성 | 동일 final_equity |

## 금융 규제 케이스 (COMPLIANCE.md)

- **비선형 추정**: NLW 고유값별 수축 → 극단 고유값 과대추정 보정(소표본).
- **수렴 안정**: 병렬 롤아웃 분산 감소 + LR 감쇠 → 후반 미세조정.
- **점진 복구**: rate ramp → 복구 직후 부하 급증 방지(트래픽 단계 증대).
- **정상성 보장**: VAR 안정성 사영(|λ|<1) → 발산 방지, Yule-Walker 안정 추정.
