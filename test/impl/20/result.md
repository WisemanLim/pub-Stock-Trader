# test/impl/20 — 차수 20 고도화 시험 결과

**판정: PASS (364/364)**
**일시: 2026-06-07**

## 총괄

| 영역 | 서비스 | 러너 | 결과 |
|------|--------|------|------|
| MPM-RL 영속풀+공유메모리 + 기존 | analysis | pytest | ✅ 119 |
| F1.2 AIMD·우선순위큐·백프레셔 + 기존 | ingest | pytest | ✅ 97 |
| RAG | rag | pytest | ✅ 10 |
| F3.3 자가교정 + F6.3 제어 + 기존 | agents | pytest | ✅ 36 |
| F6.3 halt·긴급청산 + 기존 | risk-engine | cargo | ✅ 67 |
| TUI | apps/tui | cargo | ✅ 9 |
| F6.2 캔들차트 + 기존 | web(dashboard+bff) | vitest | ✅ 26 |
| **합계** | | | **✅ 364 passed, 0 failed** |

## 실행 로그

```
ingest     : 97 passed  (+ F1.2 AIMD·우선순위큐·백프레셔 14)
analysis   : 119 passed (+ MPM-RL 영속풀·공유메모리 3)
rag        : 10 passed
agents     : 36 passed  (+ F3.3 자가교정 15 + F6.3 제어 12)
risk-engine: 67 passed  (+ F6.3 halt·긴급청산 6)
tui        :  9 passed
web        : 26 passed  (dashboard 16[+캔들 11] + bff 10[+clampDays 4])
```

차수19 287 → 차수20 364 (+77).

## 구현 요약

| 기능 | 구현 |
|------|------|
| MPM-RL 영속 워커풀 | `dpg_backtest.py`: `_rollout_core`(공통 코어 추출, process·persistent 동일) + `_shm_rollout`(SharedMemory 매핑) + `_persistent_pool`/`shutdown_persistent_pool`(모듈 영속 풀). `executor="persistent"`: px/rsi 를 `SharedMemory` 1회 적재(에피소드 불변), 풀 재사용(매 에피소드 재생성 제거), 부모 unlink 책임. 순차·process 와 동일 `final_equity`(결정적) |
| F3.3 자가교정 | `self_correction.py`: `flip_rate`(BUY↔SELL 전환율) + `detect_drift`(churn·저신뢰·비중위반) + `correct_decision`(상한 클램프·HOLD 강등) + `StrategyMonitor`(이력 deque, 교정 폐환). API `POST /agents/self_correct` |
| F6.3 제어(risk) | `paper.rs`: `PaperBook.halted` + `set_halt`/`is_halted`/`liquidate(prices)`. `main.rs`: `/control/halt`·`/control/status`·`/control/liquidate`(전종목 시장가 매도+자동 halt, best-effort DB 영속). `paper_execute` halt 시 신규주문 차단. 청산은 halt 독립(Fail-Safe) |
| F6.3 제어(agents) | `control.py`: `parse_command`(/stop·/resume·/liquidate·/status) + `authorized`(control_secret 정확일치, 미설정 전거부) + `execute_command`(risk-engine 위임). API `/control/command`·`/control/telegram`(헤더/쿼리 시크릿) |
| F1.2 AIMD | `adaptive_flow.py`: `AIMDRateController`(가산증가·승법감소·클램프, 톱니파) + `PriorityCommandQueue`(우선순위+FIFO heapq, 백프레셔 워터마크, 용량초과 최저우선 드롭) |
| F6.2 캔들 | dashboard `lib/candles.ts`(priceRange·scaleY·candleLayout·applyLivePrice 실시간) + `CandleChart.tsx`(SVG 무의존, BFF 폴링) + bff `clampDays`·`/api/candles` 프록시 |
| MPM-dev | `Procfile.dev`(ingest·analysis·rag·agents·risk·web 6프로세스) + `make dev-all`(uvx honcho 무설치). `honcho check` → Valid |

## 규제 적합(COMPLIANCE/finance)

- **무권한 제어 방지**(전자금융거래법): F6.3 인바운드 제어는 `control_secret` 정확 일치 필수, 미설정 시 전 거부(`test_secret_unset_rejects_all`).
- **append-only 원장**: 긴급 청산 체결도 원장 기록 + best-effort DB 영속(거래기록 보존).
- **Fail-Safe / DR-BCP**(F4 연계): halt(긴급 중지)와 청산을 분리 — 중지 상태에서도 청산 가능(`liquidate_works_even_when_halted`).
- **결정성(감사 가능)**: RL(시드)·자가교정(입력열)·AIMD(상태) 모두 결정적.

## 픽스 이력

- 무수정 1회 통과(0 fail). 신규 모듈은 기존 패턴(now_fn 주입·mock·no-op 폴백·결정적 시드) 준수.

## 검증 커맨드

```bash
cd services/ingest   && uv run pytest -q     # 97
cd services/analysis && uv run pytest -q     # 119
cd services/rag      && uv run pytest -q     # 10
cd services/agents   && uv run pytest -q     # 36
cargo test --workspace                       # risk 67 + tui 9
cd web && pnpm -r test                       # dashboard 16 + bff 10
uvx --from honcho honcho check -f Procfile.dev   # Valid (6 procs)
```
