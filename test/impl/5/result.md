# test/impl/5 — 차수 5 고도화 시험 결과

**판정: PASS (124/124)**
**일시: 2026-06-07**

## 총괄

| 영역 | 서비스 | 러너 | 결과 |
|------|--------|------|------|
| LSTM 재학습·Transformer + RL 백테스팅 + 기존 | analysis | pytest | ✅ 31 |
| 브로커 인증·재연결 + 기존 | ingest | pytest | ✅ 37 |
| pgvector + 인메모리 | rag | pytest | ✅ 10 |
| 알림 + 멀티에이전트 | agents | pytest | ✅ 9 |
| 리스크 + 가상체결 + 종목별 실현손익 | risk-engine | cargo | ✅ 20 |
| TUI | apps/tui | cargo | ✅ 9 |
| Web | web | vitest | ✅ 8 |
| **합계** | | | **✅ 124 passed, 0 failed** |

## 실행 로그

```
ingest    : 37 passed (30 + 7 broker auth)
analysis  : 31 passed (21 + 5 transformer/retrain + 5 RL)
rag       : 10 passed (pgvector 4 실연동)
agents    :  9 passed
risk-engine: 20 passed (19 + 1 종목별 실현손익)
tui        :  9 passed
web        :  8 passed
```

## 구현 요약

| 기능 | 구현 |
|------|------|
| LSTM 스케줄 재학습 | `needs_retrain`(trained_at 신선도)·`scheduled_retrain`(stale만 학습), `POST /predict/retrain` |
| Transformer | `_Transformer`(인코더+위치임베딩), arch=transformer, `model=transformer` 예측, 체크포인트 왕복 |
| 강화학습 백테스팅 | 테이블 Q-learning(RSI버킷×보유 상태, 3행동), 학습→그리디 평가, 시드 결정적, `POST /backtest/rl` |
| 브로커 인증·재연결 | `build_auth_message`(generic/kis)·`backoff_delay`(지수)·`should_retry`, broker_feed 재연결 래퍼 |
| 종목별 실현손익 | `realized_by_ticker` HashMap, `realized_for(ticker)`, portfolio 노출 |

## 픽스 이력

- 없음(신규 추가 위주, 기존 회귀 통과).

## MVP 범위 한계 (다음 차수 후보)

- LSTM/Transformer: 단일 종목·고정 하이퍼파라미터 — 멀티변량(거래량·지표) 입력·튜닝 미적용.
- RL: 테이블 Q-learning(이산 상태) — DQN·연속행동·포지션 사이징 미적용.
- 브로커 재연결: 백오프·인증 골격 — 실 브로커 토큰 만료 갱신·하트비트 핑퐁 미구현.
- 종목별 손익: 실현손익 분리 — 종목별 미실현·일별 손익 곡선·세금 처리 미적용.
