# test/impl/22 — 차수 22 시험 시나리오

**대상:** F2.2 예측 고도화 — 적응 격자 QuEST · Marchenko-Pastur 적합도검정 · 팩터모델 타깃.
PRD 다음 단계 "F2.2 고도화(적응 격자 QuEST·MP 적합도검정·factor model 타깃)" 완료.
**모두 가산(additive)** — 기존 함수·모드 무변경, 신규 target/mode 추가 → 무회귀.

## 구현 (channels.py)

1. `_quest_adaptive_shrink(sample, n, grid=200)` — 균일 격자(_quest_grid_shrink) 대신
   표본 고유값 분위수로 격자 배치(밀집 구간 노드 집중). 밀도 f·Hilbert Hf per-node 평균
   (비균일 격자 무관) → oracle 고유값 보간. target=`quest_adaptive`, mode=`erc_quest_adaptive`.
2. `marchenko_pastur_gof(eigs, c, bins=50)` — 표본 고유값 분포 vs MP 법칙 KS 거리(0~1).
   MP 지지 [(1±√c)²]·σ². 낮을수록 노이즈(MP) 적합=신호 적음. 소표본·c∉(0,1) → 1.0.
3. `_factor_model_shrink(sample, n)` — MP 상한 λ⁺=σ²(1+√c)² 초과 고유값=신호 보존,
   bulk(노이즈)는 평균 평탄화(RMT 디노이징). target=`factor_model`, mode=`erc_factor`.

## 시나리오 (검증 케이스)

| # | 테스트 | 검증 |
|---|--------|------|
| 1 | `test_quest_adaptive_valid_oracle` | 적응 격자 출력 PSD·대칭·양 고유값·유한 |
| 2 | `test_quest_adaptive_small_sample_fallback` | p>n → 원본 반환(보수) |
| 3 | `test_quest_adaptive_finite_and_psd_on_larger`(=valid_oracle) | 5×60 유효 oracle |
| 4 | `test_mp_gof_lower_for_pure_noise_than_spiked` | 순노이즈 GOF < 스파이크 GOF(신호 검출) |
| 5 | `test_mp_gof_invalid_inputs` | 표본부족·c범위밖 → 1.0 |
| 6 | `test_factor_model_shrink_preserves_signal_flattens_bulk` | 최대(신호) 고유값 보존 + bulk 평탄화(std≈0) |
| 7 | `test_factor_model_no_signal_returns_original` | p>n → 원본 |
| 8 | `test_macro_erc_quest_adaptive_combine` | erc_quest_adaptive 합성 유한 |
| 9 | `test_macro_erc_factor_combine` | erc_factor 합성 유한 |

## 규제(COMPLIANCE/finance)
- 결정성: 시드 고정 + 분위수/MP 격자 결정적 → 동일 입력 동일 결과(감사 가능, 모델 버전 고정).
- 외부 의존(FDR) mock, 전 심볼 실패 시 중립 폴백 유지.

## 판정 기준
- analysis pytest 전건 PASS, 기존 채널/예측/RL 무회귀.
