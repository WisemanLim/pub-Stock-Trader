# test/impl/11 — 차수 11 고도화 시험 결과

**판정: PASS (211/211)**
**일시: 2026-06-07**

## 총괄

| 영역 | 서비스 | 러너 | 결과 |
|------|--------|------|------|
| 동적 가중·증분 PCA + QR-DQN/IQN + 기존 | analysis | pytest | ✅ 75 |
| 실 WS 송신·ack + 기존 | ingest | pytest | ✅ 64 |
| pgvector + 인메모리 | rag | pytest | ✅ 10 |
| 알림 + 멀티에이전트 | agents | pytest | ✅ 9 |
| 리스크 + 5요인·Newey-West | risk-engine | cargo | ✅ 36 |
| TUI | apps/tui | cargo | ✅ 9 |
| Web | web | vitest | ✅ 8 |
| **합계** | | | **✅ 211 passed, 0 failed** |

## 실행 로그

```
ingest    : 64 passed (+ ack 추적)
analysis  : 75 passed (+ dynamic/ipca 합성 + QR-DQN/IQN)
rag       : 10 passed
agents    :  9 passed
risk-engine: 36 passed (+ 5요인 Newey-West HAC)
tui        :  9 passed
web        :  8 passed
```

## 구현 요약

| 기능 | 구현 |
|------|------|
| 동적 가중·증분 PCA | `MACRO_COMBINE`=dynamic(변동성 역가중)·ipca(롤링 윈도우 SVD 제1주성분), `_dynamic_weights`·`_incremental_pca` |
| QR-DQN/IQN | `_QRNet`(ACTIONS×8 분위수)·`_IQNNet`(τ 코사인 임베딩), quantile Huber loss, argmax mean(quantiles), `POST /backtest/qrdqn?mode=qrdqn\|iqn` |
| 실 WS 송신·ack | `SubscriptionManager.parse_ack`(generic/kis)·`pending_acks`, ack_state pending→acked 추적 |
| 5요인·Newey-West | `factor_regression_nw`(Bartlett HAC SE), `invert`·`matmul` 헬퍼, `POST /paper/factor_regression_nw` |

## 픽스 이력

- factor_regression_nw 5요인 테스트: 관측 7→30점으로 늘려 식별성 확보(near-singular 회피).

## MVP 범위 한계 (다음 차수 후보)

- 동적 가중: 변동성 역가중 — 리스크 패리티·예측 기반 가중 미적용.
- 증분 PCA: 롤링 SVD 재계산 — 진성 증분 갱신(Oja/CCIPCA) 미적용.
- QR-DQN/IQN: 고정 분위수·기본 임베딩 — risk-sensitive(CVaR) 정책·FQF 미적용.
- WS ack: 추적만 — 타임아웃 재송신·구독 실패 알림 미적용.
- Newey-West: 고정 lag — 자동 대역폭(Andrews) 선택 미적용.
