# test/impl/7 — 차수 7 고도화 시험 결과

**판정: PASS (152/152)**
**일시: 2026-06-07**

## 총괄

| 영역 | 서비스 | 러너 | 결과 |
|------|--------|------|------|
| MACD·거시·뉴스 채널 + DQN 리플레이 + 기존 | analysis | pytest | ✅ 41 |
| 하트비트 핑퐁 + 기존 | ingest | pytest | ✅ 50 |
| pgvector + 인메모리 | rag | pytest | ✅ 10 |
| 알림 + 멀티에이전트 | agents | pytest | ✅ 9 |
| 리스크 + 가상체결 + 손익곡선 집계 | risk-engine | cargo | ✅ 25 |
| TUI | apps/tui | cargo | ✅ 9 |
| Web | web | vitest | ✅ 8 |
| **합계** | | | **✅ 152 passed, 0 failed** |

## 실행 로그

```
ingest    : 50 passed (43 + 7 heartbeat)
analysis  : 41 passed (37 + 4 channels + ... + 2 DQN replay)
rag       : 10 passed
agents    :  9 passed
risk-engine: 25 passed (23 + 2 equity aggregate)
tui        :  9 passed
web        :  8 passed
```

## 구현 요약

| 기능 | 구현 |
|------|------|
| MACD·거시·뉴스 채널 | FEATURES 6채널(close·volume·rsi·macd_hist·macro·news), macd_hist=종가 EMA 기반, macro·news는 `set_channel_providers` 주입(미설정 중립 0, 길이불일치 폴백) |
| DQN 리플레이·타깃넷 | `deque` 경험 리플레이 + 미니배치 학습 + 타깃 네트워크 주기 동기화(target_sync), 시드 결정적 |
| 하트비트 핑퐁 | `HeartbeatMonitor`(interval ping·timeout stale)·`build_ping_message`·`is_pong`, broker_feed recv 루프에 통합(asyncio.wait_for) |
| 손익곡선 DB·집계 | EquityPoint.ts 추가, `aggregate`(일/주 OHLC 버킷), paper_equity 테이블 영속·하이드레이션, `POST /paper/mark`(ts·DB) `GET /paper/equity_agg?period=` |

## 통합 검증 (실 postgres)

- mark 2회 → `paper_equity` 2행, `equity_agg?period=daily` OHLC 1버킷.
- 재시작 → equity_curve 2점 하이드레이션 복원.

## 픽스 이력

- 없음(멀티변량 6채널·DQN 리팩터 후 기존 회귀 전부 통과).

## MVP 범위 한계 (다음 차수 후보)

- 거시·뉴스 채널: provider 훅만 — 실 거시지표(금리·환율) 적재·뉴스 센티먼트 파이프라인 미연결.
- DQN: 단일 환경·고정 ε — ε 감쇠·Double DQN·Dueling 미적용.
- 하트비트: 단일 연결 — 다종목 멀티플렉싱·구독 갱신 미적용.
- 손익곡선 집계: 일/주 OHLC — 월·분기·벤치마크 대비 초과수익(알파) 미적용.
