# test/impl/17 — 차수 17 고도화 시험 결과

**판정: PASS (269/269)**
**일시: 2026-06-07**

## 총괄

| 영역 | 서비스 | 러너 | 결과 |
|------|--------|------|------|
| NLW 축소·병렬 롤아웃·LR 스케줄 + 기존 | analysis | pytest | ✅ 107 |
| 점진 트래픽 증대(rate ramp) + 기존 | ingest | pytest | ✅ 78 |
| pgvector + 인메모리 | rag | pytest | ✅ 10 |
| 알림 + 멀티에이전트 | agents | pytest | ✅ 9 |
| 리스크 + VAR 안정성·Yule-Walker | risk-engine | cargo | ✅ 48 |
| TUI | apps/tui | cargo | ✅ 9 |
| Web | web | vitest | ✅ 8 |
| **합계** | | | **✅ 269 passed, 0 failed** |

## 실행 로그

```
ingest    : 78 passed (+ rate ramp)
analysis  : 107 passed (+ NLW 비선형축소 + 병렬 롤아웃·LR 스케줄)
rag       : 10 passed
agents    :  9 passed
risk-engine: 48 passed (+ VAR 안정성 사영·Yule-Walker)
tui        :  9 passed
web        :  8 passed
```

## 구현 요약

| 기능 | 구현 |
|------|------|
| 비선형 축소 NLW | `_ledoit_wolf_shrink(target=nlw)` — 고유분해 후 고유값별 수축(극단↔평균, δ=c/(c+dist)), `MACRO_COMBINE=erc_nlw` |
| 병렬 롤아웃·LR 스케줄 | dpg `n_rollouts`(독립 trajectory GAE 후 concat·분산감소), `lr_final`(에피소드 선형 감쇠) |
| 점진 트래픽 증대 | `probe_ack`→ramp 시작, `ramp_allows`(한도 내 허용)·`ramp_tick`(interval마다 step 상향) |
| VAR 안정성·Yule-Walker | `spectral_radius`(거듭제곱 반복)·`stabilize_scale`(|λ|≥0.97→축소), `factor_regression_qs_var_opt(stabilize)`, `ar_yule_walker`(Levinson-Durbin) |

## 픽스 이력

- Yule-Walker 테스트: 결정적 주기 노이즈가 자기상관 왜곡 → LCG 백색노이즈로 교체.

## MVP 범위 한계 (다음 차수 후보)

- NLW: 휴리스틱 고유값 수축 — QuEST(정밀 비선형) 미적용.
- 병렬 롤아웃: 순차 수집 — 실제 멀티프로세스 병렬 미적용.
- rate ramp: 종목수 한도 — 처리율(req/s) 기반 토큰버킷 미적용.
- VAR 안정성: ΣA 스케일 사영 — companion 고유값 개별 사영 미적용.
