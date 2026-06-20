# test/impl/4 — 차수 4 고도화 시험 결과

**판정: PASS (110/110)**
**일시: 2026-06-07**

## 총괄

| 영역 | 서비스 | 러너 | 결과 |
|------|--------|------|------|
| LSTM 사전학습 + 다전략 백테스팅 + 기존 | analysis | pytest | ✅ 21 |
| 실 브로커 어댑터 + 기존 | ingest | pytest | ✅ 30 |
| pgvector + 인메모리 | rag | pytest | ✅ 10 (pgvector 4 실연동) |
| 알림 + 멀티에이전트 | agents | pytest | ✅ 9 |
| 리스크 + 가상체결 다종목 | risk-engine | cargo | ✅ 19 (10 + 9 paper) |
| TUI | apps/tui | cargo | ✅ 9 |
| Web | web | vitest | ✅ 8 |
| **합계** | | | **✅ 110 passed, 0 failed** |

## 실행 로그

```
ingest    : 30 passed (21 + 9 broker adapters)
analysis  : 21 passed (8 base + 9 backtest 다전략 + 4 lstm 사전학습)
rag       : 10 passed (6 인메모리 + 4 pgvector)
agents    :  9 passed
risk-engine: 19 passed (10 risk + 9 paper 다종목)
tui        :  9 passed
web        :  8 passed (bff 3 + dashboard 5)
```

## 통합 검증 (실 인프라)

1. **가상체결 DB 영속화** — risk-engine + DATABASE_URL=postgres 기동.
   - 005930 10주·000660 5주 매수 → portfolio 2종목 표시.
   - `paper_fills` 테이블 2행 확인(append-only).
2. **재시작 하이드레이션** — 프로세스 재기동 → DB 원장 리플레이로 2종목 포지션 자동 복원(`fills:2`).
3. **pgvector** — rag 통합 4건 실 postgres 연동 통과.

## 픽스 이력

- run_backtest 시그니처 변경(short_window/long_window → strategy+params) → 기존 백테스트 테스트·API 호출 갱신.
- sqlx 0.8 재활성화(postgres only) — paper_db 영속화 모듈 추가.

## 구현 요약

| 기능 | 구현 |
|------|------|
| LSTM 사전학습 | `train_and_save`→체크포인트(.pt, lo/hi 보존), predict 시 로딩/즉석학습 폴백, `POST /predict/{t}/train` |
| 다전략 백테스팅 | sma_cross·rsi_threshold·macd_cross, 전략 레지스트리, `/backtest/strategies` |
| 브로커 어댑터 | generic·kis 프로토콜 파서, register_adapter 확장, broker_feed 연동 |
| 가상체결 다종목 | HashMap 다종목 포지션, open_positions, replay 복원 |
| 가상체결 영속화 | postgres paper_fills append-only, 시작 하이드레이션, 연결실패 시 인메모리 폴백 |

## MVP 범위 한계 (다음 차수 후보)

- LSTM: 단일 종목 즉석/사전학습 — 스케줄 자동 재학습·Transformer 앙상블 미적용.
- 백테스팅: 3개 룰베이스 전략 — 강화학습(tensortrade)·파라미터 최적화 미적용.
- 브로커 어댑터: generic/kis 파서 — 실 인증·구독·재연결·하트비트 미구현.
- 가상체결: 실현손익 종목별 분리·계정 다중화 미적용(전역 단일 realized_pnl).
