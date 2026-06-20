# test/impl/6 — 차수 6 고도화 시험 결과

**판정: PASS (139/139)**
**일시: 2026-06-07**

## 총괄

| 영역 | 서비스 | 러너 | 결과 |
|------|--------|------|------|
| 멀티변량 입력 + DQN + 기존 | analysis | pytest | ✅ 37 |
| 토큰 만료 갱신 + 기존 | ingest | pytest | ✅ 43 |
| pgvector + 인메모리 | rag | pytest | ✅ 10 |
| 알림 + 멀티에이전트 | agents | pytest | ✅ 9 |
| 리스크 + 가상체결 + 손익곡선 | risk-engine | cargo | ✅ 23 |
| TUI | apps/tui | cargo | ✅ 9 |
| Web | web | vitest | ✅ 8 |
| **합계** | | | **✅ 139 passed, 0 failed** |

## 실행 로그

```
ingest    : 43 passed (37 + 6 token manager)
analysis  : 37 passed (31 + 2 multivariate + 4 DQN)
rag       : 10 passed
agents    :  9 passed
risk-engine: 23 passed (20 + 3 mark-to-market)
tui        :  9 passed
web        :  8 passed
```

## 구현 요약

| 기능 | 구현 |
|------|------|
| 멀티변량 입력 | LSTM/Transformer input_size=F, FEATURES=[close,volume,rsi], 열별 정규화, 체크포인트에 n_features·features 보존, 롤아웃은 종가만 갱신·타 피처 고정 |
| DQN | `_QNet`(MLP), 상태=[rsi,수익률,보유], 온라인 Q 학습→그리디 평가, 시드 결정적, `POST /backtest/dqn`(async) |
| 토큰 만료 갱신 | `TokenManager`(issuer 콜백·skew 선제 재발급·invalidate), now_fn 주입 테스트 |
| 종목별 미실현 손익곡선 | `unrealized_by_ticker`·`mark`(EquityPoint 누적), `POST /paper/mark`·`GET /paper/equity_curve` |

## 픽스 이력

- 없음(멀티변량 리팩터 후 기존 회귀 전부 통과).

## MVP 범위 한계 (다음 차수 후보)

- 멀티변량: close·volume·rsi 3채널 — MACD·거시지표·뉴스센티먼트 채널 미추가, 롤아웃 시 비-종가 피처 고정(근사).
- DQN: 온라인 학습(리플레이 버퍼·타깃 네트워크 없음) — 안정화 기법 미적용.
- 토큰: 단일 토큰 관리 — 다계정·리프레시 토큰·동시성 락 미적용.
- 손익곡선: 메모리 누적 — DB 영속화·기간 집계(일/주) 미적용.
