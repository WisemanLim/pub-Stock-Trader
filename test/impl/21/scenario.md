# test/impl/21 — 차수 21 시험 시나리오

**대상:** F1.2 적응형 흐름제어(AIMD·우선순위 큐·백프레셔)를 `SubscriptionManager` 토큰버킷에 **통합**.
차수20에서 별도 모듈(`adaptive_flow.py`)로 제공한 것을 멀티플렉서 런타임에 결합(잔여 항목 완료).

## 구현

- `broker_multiplex.py` `SubscriptionManager` 옵트인 파라미터 추가:
  - `aimd: AIMDRateController|None` — 전역 토큰버킷 rate 를 AIMD 로 동적 구동.
    - ack 성공(`parse_ack`) → `on_success`(가산증가). 구독실패 give-up(`check_timeouts`) → `on_loss`(승법감소).
    - `_tb_refill`/`current_rate` 가 `aimd.current_rate()` 로 `_tb_rate` 동기화.
  - `command_capacity`/`command_watermark` — 송신 대기 명령을 `PriorityCommandQueue` 로 관리.
    - `add(ticker, channel, priority)` 우선순위 적재, `remove` 는 우선순위 5(해지 앞당김).
    - `drain_commands` 우선순위 순서 반환. `command_backpressured()`·`commands_dropped()` 노출.
- **하위호환**: `aimd`·`command_*` 미지정 시 기존 FIFO 리스트·고정 rate 동작 그대로(기본값).

## 시나리오 (검증 케이스)

1. `test_aimd_drives_rate_up_on_ack` — ack 성공 → `current_rate` 가산증가(5→7).
2. `test_aimd_drops_rate_on_subscription_failure` — 구독 give-up → 승법감소(10→5).
3. `test_aimd_rate_feeds_token_bucket` — AIMD rate(1/s, cap2) 가 실제 버킷 소진/충전 구동.
4. `test_priority_queue_orders_commands` — drain 우선순위 순서(HIGH·MID·LOW).
5. `test_unsubscribe_prioritized_over_subscribe` — 해지가 신규 구독보다 앞당겨짐.
6. `test_command_backpressure_watermark` — 워터마크 도달 시 backpressure True.
7. `test_command_capacity_drops_lowest_priority` — 용량 초과 시 최저 우선순위 드롭 + 회계.
8. `test_default_mode_unchanged_fifo` — 기본 모드 FIFO·무제한 보존(하위호환).

## 규제(COMPLIANCE/finance)
- 흐름제어는 부분장애 격리(degrade) 강화 — 손실 시 처리율 급감으로 브로커 과부하·차단 회피(가용성·DR/BCP 정신).
- 결정성: `now_fn` 주입 + AIMD 상태머신 → 동일 입력열 동일 결과(감사 가능).

## 판정 기준
- ingest pytest 전건 PASS, 기존 멀티플렉서/토큰버킷 테스트 무회귀.
