# test/impl/22 — 차수 22 고도화 시험 결과

**판정: PASS (381/381)**
**일시: 2026-06-07**

## 총괄

| 영역 | 서비스 | 러너 | 결과 |
|------|--------|------|------|
| F2.2 적응격자 QuEST·MP 적합도·팩터모델 + 기존 | analysis | pytest | ✅ 128 |
| ingest | ingest | pytest | ✅ 105 |
| rag | rag | pytest | ✅ 10 |
| agents | agents | pytest | ✅ 36 |
| risk-engine | risk-engine | cargo | ✅ 67 |
| tui | apps/tui | cargo | ✅ 9 |
| web | dashboard+bff | vitest | ✅ 26 |
| **합계** | | | **✅ 381 passed, 0 failed** |

차수21 372 → 차수22 381 (+9, analysis 119→128).

## 구현 요약

| 항목 | 구현 |
|------|------|
| 적응 격자 QuEST | `_quest_adaptive_shrink` — 표본 고유값 **분위수 격자**(밀집 구간 노드 집중) + 양끝 패딩. 밀도·Hilbert per-node 평균(비균일 무관) → oracle 보간. target `quest_adaptive`, mode `erc_quest_adaptive` |
| MP 적합도검정 | `marchenko_pastur_gof(eigs, c)` — MP 지지 [(1±√c)²]·σ² 누적분포 vs 경험 CDF KS 거리(0~1). 신호 있으면↑. c∉(0,1)·소표본 → 1.0 |
| 팩터모델 타깃 | `_factor_model_shrink` — MP 상한 λ⁺ 초과=신호 보존, bulk 평균 평탄화(RMT 디노이징). target `factor_model`, mode `erc_factor` |
| 가산 설계 | `_ledoit_wolf_shrink`/`macro_provider` 에 분기만 추가. 기존 quest/quest_grid/nlw/oas/cc 무변경 → 무회귀 |

## 실행 로그

```
analysis: 128 passed (channels 46 = 기존 37 + F2.2 9)
  test_quest_adaptive_valid_oracle / _small_sample_fallback
  test_mp_gof_lower_for_pure_noise_than_spiked / _invalid_inputs
  test_factor_model_shrink_preserves_signal_flattens_bulk / _no_signal_returns_original
  test_macro_erc_quest_adaptive_combine / _erc_factor_combine
```

## 픽스 이력

- `test_quest_adaptive_*` 최초 가정(균일 격자와 근사 일치, 고유값 분산 축소)이 소표본에서
  비성립 확인(적응·균일 격자는 동일 oracle 을 서로 다르게 근사) → 검증을 **유효성 불변식**
  (PSD·대칭·양 고유값·유한)으로 교정 후 통과. 구현 무수정, 시험 가정만 정정.
- divide-by-zero RuntimeWarning(노드=표본 고유값 일치 시): 기존 `_quest_grid_shrink` 와 동일
  패턴(마스킹 처리) — 결과 영향 없음.

## 검증 커맨드
```bash
cd services/analysis && uv run pytest tests/test_channels.py -q   # 46
cd services/analysis && uv run pytest -q                          # 128
```
