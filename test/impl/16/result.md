# test/impl/16 — 차수 16 고도화 시험 결과

**판정: PASS (259/259)**
**일시: 2026-06-07**

## 총괄

| 영역 | 서비스 | 러너 | 결과 |
|------|--------|------|------|
| OAS·상수상관 타깃·PPO 강화 + 기존 | analysis | pytest | ✅ 102 |
| half-open 탐침 + 기존 | ingest | pytest | ✅ 76 |
| pgvector + 인메모리 | rag | pytest | ✅ 10 |
| 알림 + 멀티에이전트 | agents | pytest | ✅ 9 |
| 리스크 + full VAR(p)·BIC/HQ | risk-engine | cargo | ✅ 45 |
| TUI | apps/tui | cargo | ✅ 9 |
| Web | web | vitest | ✅ 8 |
| **합계** | | | **✅ 259 passed, 0 failed** |

## 실행 로그

```
ingest    : 76 passed (+ half-open 탐침 송신)
analysis  : 102 passed (+ OAS·상수상관 타깃·PPO minibatch/엔트로피/KL)
rag       : 10 passed
agents    :  9 passed
risk-engine: 45 passed (+ full VAR(p)·BIC/HQ 차수선택)
tui        :  9 passed
web        :  8 passed
```

## 구현 요약

| 기능 | 구현 |
|------|------|
| OAS·상수상관 타깃 | `_const_corr_target`(평균상관 r̄), `_ledoit_wolf_shrink(target=identity\|const_corr\|oas)`, OAS 폐형 δ(Chen 2010), `MACRO_COMBINE=erc_cc\|erc_oas` |
| PPO 강화 | minibatch SGD(시드 순열), 엔트로피 보너스(entropy_coef), KL 조기종료(kl_target) |
| half-open 탐침 | `probe`(half_open 단일 탐침 송신·중복방지), `probe_ack`→closed·`probe_fail`→재open |
| full VAR(p)·BIC/HQ | `var_fit`(다변량 OLS), `var_order_select`(잔차공분산 det IC), `det` 헬퍼, `factor_regression_qs_var(criterion=aic\|bic\|hq)` |

## 픽스 이력

- 없음(신규 추가, 기존 회귀 전부 통과).

## 거시 합성 모드 (총 12종)
mean·weighted·dynamic·riskparity·erc·erc_newton·erc_lw·erc_cc·erc_oas·pca·ipca·ccipca

## MVP 범위 한계 (다음 차수 후보)

- OAS: μI 타깃 OAS — 비선형 축소(NLW)·factor model 타깃 미적용.
- PPO: 단일 환경 — 병렬 롤아웃·GAE 정규화 클립·LR 스케줄 미적용.
- half-open: 단일 탐침 — 점진 트래픽 증대(rate ramp) 미적용.
- VAR(p): full VAR + IC — 안정성(고유값) 사영·Yule-Walker 미적용.
