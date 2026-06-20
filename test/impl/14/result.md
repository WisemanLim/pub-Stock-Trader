# test/impl/14 — 차수 14 고도화 시험 결과

**판정: PASS (240/240)**
**일시: 2026-06-07**

## 총괄

| 영역 | 서비스 | 러너 | 결과 |
|------|--------|------|------|
| ERC Newton·분포형 정책그라디언트 + 기존 | analysis | pytest | ✅ 91 |
| 종목별 서킷브레이커 + 기존 | ingest | pytest | ✅ 72 |
| pgvector + 인메모리 | rag | pytest | ✅ 10 |
| 알림 + 멀티에이전트 | agents | pytest | ✅ 9 |
| 리스크 + full VAR prewhitening | risk-engine | cargo | ✅ 41 |
| TUI | apps/tui | cargo | ✅ 9 |
| Web | web | vitest | ✅ 8 |
| **합계** | | | **✅ 240 passed, 0 failed** |

## 실행 로그

```
ingest    : 72 passed (+ 종목별 서킷브레이커)
analysis  : 91 passed (+ ERC Newton·DPG)
rag       : 10 passed
agents    :  9 passed
risk-engine: 41 passed (+ full VAR(1) prewhitening)
tui        :  9 passed
web        :  8 passed
```

## 구현 요약

| 기능 | 구현 |
|------|------|
| ERC 정밀해 Newton | `_erc_newton`(Spinu 2013 볼록 ½xᵀΣx−c·Σln xᵢ, Newton step + 양수 백트래킹), `MACRO_COMBINE=erc_newton` |
| 분포형 정책 그라디언트 | `_Policy`(softmax) + `_DistCritic`(상태가치 분위수), REINFORCE + 분포 critic baseline·quantile Huber, `POST /backtest/dpg` |
| 종목별 서킷브레이커 | `_ticker_cb_open` dict, `ticker_circuit_open`(종목별 cooldown), 실패 시 종목 open + router 제거(재구독 가능) |
| full VAR(1) prewhitening | `factor_regression_qs_full(full_var=true)` — A=M0·M1⁻¹ 행렬 백색화 → recolor D=(I−A)⁻¹ S D' |

## 픽스 이력

- 종목별 서킷 재구독 위해 실패 시 router.unsubscribe 추가(cooldown 후 add 가능).

## 누적 RL 백테스트 전략 (9종)
qlearn · dqn(Rainbow급) · c51 · qrdqn · iqn · fqf(전역/상태의존) · dpg(분포형 정책그라디언트) + CVaR risk-sensitive 옵션.

## MVP 범위 한계 (다음 차수 후보)

- ERC Newton: 정적 공분산 — Ledoit-Wolf 축소·동적 공분산 미적용.
- DPG: REINFORCE baseline — PPO/A2C·GAE 미적용.
- 서킷브레이커: 종목·전역 2계층 — 채널별·반개방 탐침 미적용.
- VAR prewhiten: full VAR(1) — 차수선택(AIC)·안정성 사영 미적용.
