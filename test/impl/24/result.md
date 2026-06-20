# test/impl/24 — 차수 24 MPM 고도화 시험 결과

**판정: PASS (401/401)**
**일시: 2026-06-07**

## 총괄

| 영역 | 러너 | 결과 |
|------|------|------|
| RL 영속 풀 고도화 + 기존 (analysis) | pytest | ✅ 131 |
| MPM Procfile 생성기 (tools/mpm) | pytest(standalone) | ✅ 12 |
| ingest | pytest | ✅ 105 |
| rag | pytest | ✅ 10 |
| agents | pytest | ✅ 36 |
| risk-engine | cargo | ✅ 72 |
| tui | cargo | ✅ 9 |
| web | vitest | ✅ 26 |
| **합계** | | **✅ 401 passed, 0 failed** |

차수23 386 → 차수24 401 (+15: analysis +3, tools/mpm +12). clean.

## 구현 요약

| 항목 | 구현 |
|------|------|
| MPM 생성기 | `tools/mpm/mpm.py` — `SERVICES` 레지스트리 → ENV·그룹별 honcho Procfile 결정적 생성. `render_procfile`/`services_for`/`validate` + CLI(`--env/--group/--check`). 그룹 py·rust·web. 표준 라이브러리만 |
| Makefile | `make mpm-up ENV=dev GROUP="py rust"`(생성→honcho), `make mpm-check`(검증). 정적 `dev-all` 유지(하위호환). `Procfile.dev.gen` gitignore |
| RL 풀 워커수 | `BACKTEST_PERSIST_WORKERS` env 우선 + `persistent_pool_stats()`(활성·워커수) |
| RL 풀 복원력 | `_persistent_map` — `BrokenProcessPool` 시 풀 폐기·재생성·재시도. graceful shutdown + stats 리셋 |

## 실행 로그

```
analysis : 131 passed (RL 풀 stats/env워커/재생성 3 추가)
tools/mpm: 12 passed  (analysis .venv pytest 로 실행, stdlib 전용)
make mpm-check ENV=dev GROUP=py → exit 0
honcho check (생성 Procfile) → Valid (ingest, analysis, rag, agents, risk, web)
make -n mpm-up GROUP="py rust" → --group py --group rust 정상 확장
```

## 검증 커맨드
```bash
# RL 풀
cd services/analysis && uv run pytest tests/test_lstm_backtest.py -k persistent -q
# MPM 생성기(임의 uv venv pytest, stdlib 전용)
cd tools/mpm && /…/services/analysis/.venv/bin/python -m pytest test_mpm.py -q
# 생성·검증
make mpm-check ENV=dev GROUP=py
python3 tools/mpm/mpm.py --env dev | uvx --from honcho honcho check -f /dev/stdin
```

## 픽스 이력
- 무수정 1회 통과(0 fail). `_persistent_map` 도입으로 dpg_backtest persistent 분기의 미사용 `_pool` 변수 제거(lint 청결).

## 비고
- tools/mpm 은 루트 데브 도구 → 전용 venv 없이 기존 서비스 venv 의 pytest 로 실행(추가 의존 0).
  `make test` 표준 타겟에는 미포함(서비스 단위 시험 표준 유지). 별도 커맨드로 검증.
