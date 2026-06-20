# test/impl/12 — 차수 12 고도화 시험 결과

**판정: PASS (223/223)**
**일시: 2026-06-07**

## 총괄

| 영역 | 서비스 | 러너 | 결과 |
|------|--------|------|------|
| 리스크패리티·CCIPCA + CVaR/FQF + 기존 | analysis | pytest | ✅ 82 |
| ack 타임아웃 재송신 + 기존 | ingest | pytest | ✅ 67 |
| pgvector + 인메모리 | rag | pytest | ✅ 10 |
| 알림 + 멀티에이전트 | agents | pytest | ✅ 9 |
| 리스크 + Andrews NW | risk-engine | cargo | ✅ 38 |
| TUI | apps/tui | cargo | ✅ 9 |
| Web | web | vitest | ✅ 8 |
| **합계** | | | **✅ 223 passed, 0 failed** |

## 실행 로그

```
ingest    : 67 passed (+ ack 타임아웃 재송신)
analysis  : 82 passed (+ riskparity/ccipca + CVaR/FQF)
rag       : 10 passed
agents    :  9 passed
risk-engine: 38 passed (+ Andrews 자동 대역폭)
tui        :  9 passed
web        :  8 passed
```

## 구현 요약

| 기능 | 구현 |
|------|------|
| 리스크패리티·CCIPCA | `MACRO_COMBINE`=riskparity(역변동성 정규화)·ccipca(Weng 2003 covariance-free 증분 PCA), `_risk_parity_weights`·`_ccipca` |
| CVaR/FQF | `q_value` cvar_alpha 하위분위수 평균(risk-sensitive 행동), mode=fqf 분위수 비율(fraction) 학습(softmax cumsum 중점), `?cvar_alpha=` |
| ack 타임아웃 재송신 | `check_timeouts`(ack_timeout 경과 재송신)·`max_resend` 초과 failed·`failed_subscriptions`, now_fn 주입 |
| Andrews 자동 대역폭 | `andrews_bandwidth`(잔차 AR(1) ρ → Bartlett 최적 lag), `factor_regression_nw_auto`, `POST /paper/factor_regression_nw_auto` |

## 픽스 이력

- 없음(신규 추가, 기존 회귀 전부 통과).

## 누적 강화학습 백테스트 전략
qlearn(테이블) · dqn(Rainbow급: Double·Dueling·PER·n-step·Noisy) · c51(분포) · qrdqn · iqn · fqf(분위수 비율) + CVaR risk-sensitive 옵션.

## MVP 범위 한계 (다음 차수 후보)

- 리스크패리티: 역변동성 근사 — 공분산 기반 ERC(반복 최적화) 미적용.
- FQF: 전역 분위수 비율 — 상태의존 fraction proposal net 미적용.
- ack: 타임아웃 재송신 — 지수 백오프 재송신 간격·서킷브레이커 미적용.
- Andrews: AR(1) prewhitening only — VAR prewhitening·QS 커널 미적용.
