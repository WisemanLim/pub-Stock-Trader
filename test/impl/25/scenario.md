# test/impl/25 — 차수 25 시험 시나리오

**대상:** (1) bff `process` TS 오류 수정, (2) `make mpm` 백그라운드 일괄 기동·관리.
사용자 보고: `make mpm` 실행 시 bff TS2580(`Cannot find name 'process'`) 6건 → BFF(:3002) 미기동 →
대시보드 "BFF 연결 실패". 요구: 전 프로세스 백그라운드 기동 + 관리.

## 구현

### 1. bff 타입 수정 (web/apps/bff)
- `package.json` devDeps `@types/node`(22.x) 추가, `tsconfig.json` `types:["node"]`.
- `process.env.BFF_PORT` 타입 해소 → `tsc --noEmit` clean → nest 기동 정상.
- (복구) offline 설치가 web/node_modules purge → 네트워크 `pnpm install`(사용자 승인) 복구.

### 2. MPM 백그라운드 관리자 (tools/mpm/mpm.py + Makefile)
- mpm.py 서브커맨드: `up`(detached 기동·pid·log) / `stop` / `status` / `gen`(기본).
- `up`: `subprocess.Popen(start_new_session=True)` 로 honcho detached 실행, `.mpm/{Procfile.gen,mpm.pid,mpm.log}`.
- `stop`: honcho PID SIGTERM(graceful cascade) → grace 대기 → 세션 프로세스그룹 SIGTERM 잔여정리
  (detach 된 `next dev` 워커 포함). pidfile 정리.
- `status`/`pid_alive`(signal 0 probe)/`read_pid`/경로 헬퍼.
- Makefile: `make mpm [ENV= GROUP=]` · `mpm-stop` · `mpm-status` · `mpm-logs` · `mpm-check`. `.mpm/` gitignore.

## 시나리오 (검증 케이스)

| # | 검증 | 방법 |
|---|------|------|
| 1 | bff @types/node 링크 + tsc clean | `pnpm exec tsc --noEmit` exit 0 |
| 2 | web vitest 무회귀 | dashboard 16 + bff 10 |
| 3 | mpm.py 생성기/그룹/검증 (기존) | pytest 12 |
| 4 | `pid_alive` self/dead/None/0 | pytest |
| 5 | 상태경로 `.mpm/` 하위 | pytest |
| 6 | 미실행 `status`/`stop` no-op exit0 | pytest(tmp MPM_DIR) |
| 7 | **E2E**: `make mpm` → 7서비스 전부 health OK | curl 폴링 |
| 8 | bff `/api/dashboard`·`/api/candles` 실데이터 200 | curl |
| 9 | **E2E**: `make mpm-stop` → 전 포트 해제(orphan 0) | lsof |

## 규제(COMPLIANCE/finance)
- 데브 오케스트레이터 — 로컬/개발용. 실시크릿 미포함(.env 참조만). 백그라운드 pid·log `.mpm/`(gitignore).

## 판정 기준
- bff tsc clean, web 26 무회귀, tools/mpm 17 PASS, E2E 7서비스 기동·정상종료(포트 해제).
