# test/impl/10 — 차수 10 고도화 시험 결과

**판정: PASS (198/198)**
**일시: 2026-06-07**

## 총괄

| 영역 | 서비스 | 러너 | 결과 |
|------|--------|------|------|
| 가중/PCA·KR-FinBERT + C51 + 기존 | analysis | pytest | ✅ 67 |
| 실 WS 런타임 구독 + 기존 | ingest | pytest | ✅ 61 |
| pgvector + 인메모리 | rag | pytest | ✅ 10 |
| 알림 + 멀티에이전트 | agents | pytest | ✅ 9 |
| 리스크 + 롤링·Fama-French | risk-engine | cargo | ✅ 34 |
| TUI | apps/tui | cargo | ✅ 9 |
| Web | web | vitest | ✅ 8 |
| **합계** | | | **✅ 198 passed, 0 failed** |

## 실행 로그

```
ingest    : 61 passed (+ 런타임 구독 송신)
analysis  : 67 passed (+ weighted/pca 합성·KR-FinBERT·C51)
rag       : 10 passed
agents    :  9 passed
risk-engine: 34 passed (+ 롤링·Fama-French OLS)
tui        :  9 passed
web        :  8 passed
```

## 구현 요약

| 기능 | 구현 |
|------|------|
| 가중/PCA 합성 | `MACRO_COMBINE`=mean\|weighted\|pca, weighted=정규화 가중평균, pca=numpy SVD 제1주성분 z-score |
| KR-FinBERT | `_finbert_score` 한글 라벨(긍정/부정)·LABEL_0/2 대응, `FINBERT_MODEL=snunlp/KR-FinBert-SC` 교체 가능 |
| Distributional C51 | `_C51Net`(ACTIONS×N_ATOMS softmax), projected Bellman 분포 업데이트, argmax E[Z], `POST /backtest/c51` |
| 실 WS 런타임 구독 | `SubscriptionManager`(router + 명령 큐), add/remove → sub/unsub 메시지 적재, drain_commands 로 스트림 송신 |
| 롤링·Fama-French | `port_returns`·`risk_metrics_rolling`(윈도우별), `factor_regression`(OLS via Gauss-Jordan), `/paper/risk_rolling`·`/paper/factor_regression` |

## 픽스 이력

- risk_metrics 를 `metrics_from_returns` 헬퍼로 리팩터(롤링과 공유), 회귀 통과.

## MVP 범위 한계 (다음 차수 후보)

- 합성: 정적 가중·배치 PCA — 동적 가중(시변)·증분 PCA 미적용.
- C51: 고정 [v_min,v_max]·N_ATOMS — QR-DQN·IQN(분위수) 미적용.
- 런타임 구독: 명령 큐 골격 — 실 WS 송신 통합·ack 처리 미적용.
- Fama-French: 정적 OLS — 롤링 베타·5요인(RMW·CMA)·Newey-West 표준오차 미적용.
