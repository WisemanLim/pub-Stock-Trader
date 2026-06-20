# test/impl/21 — 차수 21 통합 시험 결과

**판정: PASS (372/372)**
**일시: 2026-06-07**

## 총괄

| 영역 | 서비스 | 러너 | 결과 |
|------|--------|------|------|
| F1.2 AIMD·우선순위큐·백프레셔 **통합** + 기존 | ingest | pytest | ✅ 105 |
| analysis | analysis | pytest | ✅ 119 |
| rag | rag | pytest | ✅ 10 |
| agents | agents | pytest | ✅ 36 |
| risk-engine | risk-engine | cargo | ✅ 67 |
| tui | apps/tui | cargo | ✅ 9 |
| web | dashboard+bff | vitest | ✅ 26 |
| **합계** | | | **✅ 372 passed, 0 failed** |

차수20 364 → 차수21 372 (+8, ingest 97→105).

## 구현 요약

| 항목 | 구현 |
|------|------|
| AIMD 통합 | `SubscriptionManager(aimd=...)` — 전역 토큰버킷 `_tb_rate` 를 `aimd.current_rate()` 로 구동. `parse_ack` 성공 → `on_success`(가산증가), `check_timeouts` give-up → `on_loss`(승법감소). `_tb_refill`/`current_rate()` 동기화 |
| 우선순위 큐 통합 | `command_capacity`/`command_watermark` 옵트인 → `_pending` 을 `PriorityCommandQueue` 로. `add(...,priority)`·`remove`(우선순위5)·`drain_commands`(우선순위 순서). `_enqueue`/`_dequeue_all` 추상화 |
| 백프레셔 | `command_backpressured()`(워터마크) + `commands_dropped()`(용량초과 최저우선 드롭 회계) |
| 하위호환 | 옵트인 파라미터 미지정 시 기존 FIFO 리스트·고정 rate 동작 보존. 기존 멀티플렉서/토큰버킷 33건 무회귀 |

## 실행 로그

```
ingest: 105 passed (멀티플렉서 41 = 기존 33 + 통합 8)
  test_aimd_drives_rate_up_on_ack / _drops_rate_on_subscription_failure / _rate_feeds_token_bucket
  test_priority_queue_orders_commands / _unsubscribe_prioritized_over_subscribe
  test_command_backpressure_watermark / _command_capacity_drops_lowest_priority
  test_default_mode_unchanged_fifo
```

## 픽스 이력
- 무수정 1회 통과(0 fail). 옵트인 설계로 기존 동작 불변(하위호환).

## 검증 커맨드
```bash
cd services/ingest && uv run pytest tests/test_broker_multiplex.py -q   # 41
cd services/ingest && uv run pytest -q                                  # 105
```
