# test/impl/15 — 차수 15 고도화 시험 결과

**판정: PASS (249/249)**
**일시: 2026-06-07**

## 총괄

| 영역 | 서비스 | 러너 | 결과 |
|------|--------|------|------|
| Ledoit-Wolf·PPO/A2C + 기존 | analysis | pytest | ✅ 96 |
| 채널별 서킷브레이커 + 기존 | ingest | pytest | ✅ 74 |
| pgvector + 인메모리 | rag | pytest | ✅ 10 |
| 알림 + 멀티에이전트 | agents | pytest | ✅ 9 |
| 리스크 + AIC VAR 차수선택 | risk-engine | cargo | ✅ 43 |
| TUI | apps/tui | cargo | ✅ 9 |
| Web | web | vitest | ✅ 8 |
| **합계** | | | **✅ 249 passed, 0 failed** |

## 실행 로그

```
ingest    : 74 passed (+ 채널별 서킷브레이커)
analysis  : 96 passed (+ Ledoit-Wolf·PPO/A2C GAE)
rag       : 10 passed
agents    :  9 passed
risk-engine: 43 passed (+ AIC AR 차수선택 prewhitening)
tui        :  9 passed
web        :  8 passed
```

## 구현 요약

| 기능 | 구현 |
|------|------|
| Ledoit-Wolf 축소 | `_ledoit_wolf_shrink`(sample→μI 타깃 수축, δ 최적강도), `_cov_from_zs(shrink=True)`, `MACRO_COMBINE=erc_lw` |
| PPO/A2C·GAE | dpg `mode=reinforce\|a2c\|ppo`, GAE(λ) advantage, PPO ratio clip + 다중 epoch, advantage 정규화 |
| 채널별 서킷브레이커 | `_channel_open`·`channel_circuit_open`, `add(ticker, channel)`, `channel_threshold` 분리, 채널 실패 카운트 |
| AIC VAR 차수선택 | `aic_ar_order`(AR(p) AIC 최소), `ar_ols`, `factor_regression_qs_aic`(선택 차수 대각 AR(p) prewhiten) |

## 픽스 이력

- 채널·전역 임계 분리(`channel_threshold`) — 전역 오픈이 채널 테스트 간섭하던 문제 해소.

## 누적 RL 백테스트 (정책 모드 포함)
qlearn·dqn(Rainbow급)·c51·qrdqn·iqn·fqf(전역/상태의존)·dpg(reinforce/a2c/ppo) + CVaR.

## MVP 범위 한계 (다음 차수 후보)

- Ledoit-Wolf: 대각 타깃·간이 δ — OAS·상수상관 타깃 미적용.
- PPO: 단일 배치·엔트로피 보너스 없음 — minibatch SGD·KL 조기종료 미적용.
- 서킷브레이커: 3계층(종목·채널·전역) — half-open 탐침 송신 통합 미적용.
- AIC: 대각 AR(p) — full VAR(p)·BIC/HQ 기준 미적용.
