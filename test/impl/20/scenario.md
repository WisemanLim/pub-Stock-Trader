# test/impl/20 — 차수 20 시험 시나리오

**대상 구현(다음 단계 6종):**

| # | 기능 | 서비스 | 러너 |
|---|------|--------|------|
| 1 | MPM-RL: 영속 워커풀 + 공유메모리(SharedMemory) 텐서 | analysis | pytest |
| 2 | F3.3 전략 자가교정 루프(드리프트 감시) | agents | pytest |
| 3 | F6.3 양방향 제어 — 봇 중지/긴급청산 원격 제어 | risk-engine + agents | cargo + pytest |
| 4 | F1.2 AIMD 적응형 처리율 + 우선순위 큐 + 백프레셔 | ingest | pytest |
| 5 | F6.2 실시간 캔들 차트 위젯 | web(dashboard+bff) | vitest |
| 6 | MPM-dev: honcho Procfile 오케스트레이터 + `make dev-all` | 루트 | honcho check |

## 시나리오

### 1. MPM-RL (analysis/dpg_backtest.py)
- `executor="persistent"` 추가: px/rsi 를 `SharedMemory` 에 1회 적재, 영속 `ProcessPoolExecutor` 재사용.
- 검증:
  - `test_persistent_pool_matches_sequential` — 순차와 동일 `final_equity`(결정적).
  - `test_persistent_pool_reused_across_calls` — 두 호출이 동일 풀 객체 재사용(재생성 없음).
  - `test_persistent_matches_process_executor` — process·persistent 동일 코어(`_rollout_core`) → 동일 결과.

### 2. F3.3 자가교정 (agents/self_correction.py)
- 드리프트 판정: 시그널 churn(전환율≥0.5) · 신뢰도 저하(<0.45) · 비중상한 위반.
- 교정: 비중 상한 클램프 + 불안정 시 HOLD 강등. `StrategyMonitor` 로 교정 결과를 이력에 반영(폐환).
- 검증: `flip_rate`·`detect_drift`·`correct_decision`·`StrategyMonitor`·API `/agents/self_correct` (clean/breach/unknown).

### 3. F6.3 양방향 제어 (risk-engine + agents)
- risk-engine: `PaperBook.halted` + `set_halt`/`is_halted`/`liquidate(prices)`. `/control/halt`·`/control/status`·`/control/liquidate`. halt 시 신규 주문 차단, 청산은 독립 실행(Fail-Safe).
- agents: `/control/command`·`/control/telegram` 인바운드 명령(`/stop`·`/resume`·`/liquidate`·`/status`) → risk-engine 위임.
- **규제(COMPLIANCE)**: 무권한 제어 방지(전자금융거래법) — `control_secret` 정확 일치 필수, 미설정 시 전 거부. 청산 체결도 append-only 원장 보존.
- 검증(cargo): halt 기본값·토글·청산(전종목/가격없음 보류/halt중 청산). 검증(pytest): 인증 거부·명령 위임·텔레그램 웹훅·시크릿 미설정 거부.

### 4. F1.2 AIMD (ingest/adaptive_flow.py)
- `AIMDRateController`: 성공=가산증가, 손실=승법감소, [min,max] 클램프(톱니파).
- `PriorityCommandQueue`: 우선순위 + FIFO, 백프레셔 워터마크, 용량초과 시 최저우선 드롭.
- 검증: AIMD 증가/감소/클램프/톱니/invalid · 우선순위/FIFO/drain · 백프레셔/드롭/무제한.

### 5. F6.2 캔들 차트 (web)
- dashboard `lib/candles.ts`: `candleColor`·`priceRange`·`scaleY`·`candleLayout`·`applyLivePrice`(실시간 틱 반영, 비파괴).
- `components/CandleChart.tsx`: BFF `/api/candles` 폴링 + `/api/price` 실시간 갱신, SVG 무의존 렌더.
- bff `clampDays` + `/api/candles/:ticker` → ingest `/market/ohlcv` 프록시.
- 검증(vitest): 기하 변환 11종 + clampDays 4종.

### 6. MPM-dev
- `Procfile.dev`(6 프로세스) + `make dev-all`(uvx honcho, 무설치).
- 검증: `honcho check -f Procfile.dev` → Valid, `make -n dev-all` 명령 확인.

## 판정 기준
- 전 러너(pytest·cargo·vitest) PASS, 0 fail.
- RL·교정·AIMD 결정적(시드/입력열 고정 → 동일 결과) = 감사 가능.
- 외부 의존(FDR·risk-engine·DB)은 mock/no-op 폴백.
