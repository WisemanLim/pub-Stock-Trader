# test/impl/24 — 차수 24 시험 시나리오

**대상:** MPM(multiple process manager) 고도화 — 차수20 기본판(honcho `dev-all` + 영속 풀)을 양쪽 심화.
PRD 운영 편의(개발 오케스트레이션) + F5 RL 성능. **모두 가산·하위호환**.

## 구현

### A. 데브 오케스트레이터 — `tools/mpm/mpm.py` (표준 라이브러리)
- 서비스 레지스트리(`SERVICES`) 단일 소스 → ENV·그룹별 honcho Procfile 결정적 생성.
- `render_procfile(env, groups)` · `services_for(groups)` · `validate(text)` · CLI(`--env/--group/--check`).
- 그룹: `py`(ingest·analysis·rag·agents) · `rust`(risk) · `web`. ENV 치환(APP_ENV·.env.{env}).
- Makefile: `make mpm-up ENV=dev GROUP="py rust"`(생성→honcho), `make mpm-check`(검증). 정적 `dev-all` 유지.
- `.gitignore`: `Procfile.dev.gen` 추가(common 섹션).

### B. RL 영속 풀 — `analysis/dpg_backtest.py`
- 워커수: `BACKTEST_PERSIST_WORKERS` env 우선(없으면 인자).
- `persistent_pool_stats()` — 활성/워커수 조회.
- `_persistent_map(fn, tasks, mw)` — `BrokenProcessPool`(워커 사망) 시 풀 1회 재생성 후 재시도(복원력).
- graceful `shutdown_persistent_pool`(진행 작업 대기) + stats 리셋.

## 시나리오 (검증 케이스)

| # | 테스트 | 검증 |
|---|--------|------|
| A1 | `test_render_all_groups_default_env` | 레지스트리 순서·APP_ENV=local |
| A2 | `test_env_substitution` | env=dev → APP_ENV=dev·.env.dev |
| A3 | `test_group_filter_py_only` / `_multiple` | 그룹 필터 |
| A4 | `test_unknown_group_raises` / `test_cli_unknown_group_exit2` | 무효 그룹 거부 |
| A5 | `test_validate_*` | 유효/빈/오형식 검증 |
| A6 | `test_cli_check_*` | CLI 검증 exit code |
| A7 | (수동) `make mpm-check`·honcho check generated | Valid Procfile |
| B1 | `test_persistent_pool_stats_lifecycle` | 활성/워커수/종료 후 비활성 |
| B2 | `test_persistent_pool_worker_count_from_env` | env 워커수 우선 |
| B3 | `test_persistent_map_recreates_after_shutdown` | 종료 후 재생성·동일 결과(결정적) |

## 규제(COMPLIANCE/finance)
- RL 결정성 유지(시드) — 워커수·재생성 무관 동일 결과(감사 가능).
- 데브 오케스트레이터는 로컬/개발용. 실시크릿 미포함(.env 파일 참조만).

## 판정 기준
- analysis pytest 무회귀 + RL 풀 3건. tools/mpm 12건 PASS. Makefile mpm 타겟 동작.
