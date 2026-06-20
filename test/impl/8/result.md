# test/impl/8 — 차수 8 고도화 시험 결과

**판정: PASS (175/175)**
**일시: 2026-06-07**

## 총괄

| 영역 | 서비스 | 러너 | 결과 |
|------|--------|------|------|
| 실 거시·뉴스 채널 + Double/Dueling DQN + 기존 | analysis | pytest | ✅ 54 |
| 다종목 멀티플렉싱 + 기존 | ingest | pytest | ✅ 56 |
| pgvector + 인메모리 | rag | pytest | ✅ 10 |
| 알림 + 멀티에이전트 | agents | pytest | ✅ 9 |
| 리스크 + 월/분기 집계·알파 | risk-engine | cargo | ✅ 29 |
| TUI | apps/tui | cargo | ✅ 9 |
| Web | web | vitest | ✅ 8 |
| **합계** | | | **✅ 175 passed, 0 failed** |

## 실행 로그

```
ingest    : 56 passed (50 + 6 multiplex)
analysis  : 54 passed (41 + 10 channels + 3 DQN double/dueling)
rag       : 10 passed
agents    :  9 passed
risk-engine: 29 passed (25 + 2 calendar agg + 2 alpha)
tui        :  9 passed
web        :  8 passed
```

## 구현 요약

| 기능 | 구현 |
|------|------|
| 실 거시·뉴스 파이프라인 | `channels.py` macro_provider(FDR KS11 지수·길이정렬·패딩·폴백), news_provider(ingest /news → 키워드 센티먼트 broadcast), lifespan 에서 register → lstm_model 멀티변량 입력 연결 |
| ε 감쇠·Double/Dueling DQN | `_QNet` Dueling(value+advantage), 학습 시 ε 에피소드 감쇠(epsilon_min/decay), Double DQN 타깃(online argmax + target eval), epsilon_final 반환 |
| 다종목 멀티플렉싱 | `build_subscribe_messages`(인증1+구독N)·`MultiplexRouter`(dispatch/drain), `feed_multi`·`_broker_multi_stream`, WS `/market/feed_multi/{tickers}` |
| 손익곡선 월/분기·알파 | `epoch_to_ym`(Hinnant civil), `aggregate_calendar`(month/quarter), `alpha`(port vs bench), `/paper/equity_agg?period=monthly|quarterly`·`POST /paper/alpha` |

## 픽스 이력

- aggregate_monthly_quarterly 테스트: 3번째 ts 가 같은 분기였음 → 다른 분기(Q3)로 수정.
- analysis main.py: `on_event` deprecation → `lifespan` 컨텍스트 전환.

## MVP 범위 한계 (다음 차수 후보)

- 거시·뉴스: KS11 단일 지수 + 키워드 센티먼트 — 다지표(환율·금리)·FinBERT/LLM 센티먼트·시계열 히스토리 미적용.
- DQN: Dueling+Double — PER(우선순위 리플레이)·n-step·noisy net 미적용.
- 멀티플렉싱: 단일 WS 다종목 — 종목 동적 추가/해지·백프레셔 미적용.
- 알파: 단순 초과수익 — 베타·정보비율·트래킹에러 미적용.
