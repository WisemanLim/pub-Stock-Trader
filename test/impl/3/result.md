# test/impl/3 — 고도화 기능 시험 결과

**판정: PASS (90/90)**
**일시: 2026-06-06**

## 총괄

| 영역 | 서비스 | 러너 | 결과 |
|------|--------|------|------|
| F1.2 브로커 WS + 기존 | ingest | pytest | ✅ 21 (18 + 3 broker feed) |
| F2.2 LSTM + F5 백테스팅 + 기존 | analysis | pytest | ✅ 16 (8 + 5 backtest + 3 lstm/linear) |
| F3.2 pgvector + 인메모리 | rag | pytest | ✅ 10 (6 + 4 pgvector) |
| F6.3 알림 + 기존 | agents | pytest | ✅ 9 (6 + 3 notify) |
| F4 리스크 + 가상체결 | risk-engine | cargo | ✅ 17 (10 + 7 paper) |
| F6.1 TUI | apps/tui | cargo | ✅ 9 |
| F6.2 Web | web | vitest | ✅ 8 |
| **합계** | | | **✅ 90 passed, 0 failed** |

## 실행 로그

```
ingest    : 21 passed in 0.20s
analysis  : 16 passed in 0.89s
rag       : 10 passed in 0.25s   (pgvector 4건 실 postgres 연동)
agents    :  9 passed in 0.03s
risk-engine: 17 passed (cargo)
tui        :  9 passed (cargo)
bff        :  3 passed / dashboard 5 passed (vitest)
```

## 픽스 이력

1. **torch + FastAPI 워커스레드 segfault** — sync `/predict?model=lstm` 가 anyio 워커스레드에서 torch 학습 실행 → macOS libomp 충돌로 Segmentation fault.
   - 조치 ①: prediction 엔드포인트 `async def` 전환(메인 이벤트루프 스레드 실행).
   - 조치 ②: analysis conftest `client` 픽스처에서 `with TestClient` 컨텍스트 제거(lifespan 핸들러 없음 → 포털 스레드 회피).
   - 조치 ③: lstm_model 임포트 시 `OMP_NUM_THREADS=1`, `torch.set_num_threads(1)`.
   - 조치 ④: LSTM 시험은 HTTP client 대신 `predict_lstm` 직접 호출(메인 스레드).
2. **pgvector `<=>` 연산자 미해결** — list 파라미터 타입 미지정 → operator 매칭 실패. `pgvector.Vector` 래핑으로 타입 명시.

## 검증된 신규 엔드포인트

| 엔드포인트 | 기능 |
|-----------|------|
| `GET /predict/{t}?model=lstm` | F2.2 LSTM 예측 |
| `POST /backtest/` | F5 백테스팅(MDD·Sharpe·Sortino·승률·손익비) |
| `WS /market/feed/{t}` | F1.2 브로커 틱 피드(실연동/시뮬) |
| `POST /notify/` | F6.3 Telegram/Discord 알림 |
| `POST /paper/execute` | 가상 체결(슬리피지·수수료) |
| `GET /paper/portfolio` | 가상 포지션·실현손익·체결수 |

## MVP 범위 한계 (다음 차수 후보)

- LSTM: 요청 시 즉석 학습(60 epoch) — 사전학습 체크포인트·Transformer 앙상블 미적용.
- 백테스팅: 단일 SMA 크로스 롱온리 전략 — 다전략·강화학습(tensortrade) 미적용.
- 브로커 WS: 시뮬레이션 기본 — 실 증권사 프로토콜 어댑터 미구현(URL 연결 골격만).
- 가상체결: 단일 계정·단일 종목 인메모리 — 다종목·DB 영속화·리스크엔진 게이트 자동연동 미적용.
- 알림 양방향 제어(봇 중지/긴급청산 수신) 미구현.
