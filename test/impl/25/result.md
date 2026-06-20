# test/impl/25 — 차수 25 시험 결과 (bff 타입 수정 + MPM 백그라운드 관리)

**판정: PASS (406/406 + E2E)**
**일시: 2026-06-08**

## 총괄

| 영역 | 러너 | 결과 |
|------|------|------|
| MPM 백그라운드 관리자 + 기존 (tools/mpm) | pytest(standalone) | ✅ 17 |
| web (dashboard 16 + bff 10) — bff tsc 수정 후 | vitest | ✅ 26 |
| analysis | pytest | ✅ 131 |
| ingest | pytest | ✅ 105 |
| rag | pytest | ✅ 10 |
| agents | pytest | ✅ 36 |
| risk-engine | cargo | ✅ 72 |
| tui | cargo | ✅ 9 |
| **합계** | | **✅ 406 passed, 0 failed** |
| E2E `make mpm` 기동·종료 | 수동 | ✅ 7서비스 health OK / 종료 시 전 포트 해제 |

차수24 401 → 차수25 406 (+5: tools/mpm supervisor). bff tsc 오류 0(기존 6).

## 수정/구현 요약

| 항목 | 내용 |
|------|------|
| **bff TS2580 수정** | `apps/bff/package.json` `@types/node@22.x` + `tsconfig.json` `types:["node"]`. `process.env.BFF_PORT` 해소 → `tsc --noEmit` exit 0. BFF(:3002) 정상 기동 → 대시보드 "BFF 연결 실패" 해소 |
| **node_modules 복구** | offline 설치가 web/node_modules purge(부유 버전 `19.x` 재해석으로 @types/react 미스토어) → 사용자 승인 후 네트워크 `pnpm install` 복구 |
| **MPM `up`(백그라운드)** | `subprocess.Popen(start_new_session=True)` detached honcho + `.mpm/{Procfile.gen,mpm.pid,mpm.log}`. `make mpm [ENV= GROUP=]` |
| **MPM `stop`(graceful+sweep)** | honcho PID SIGTERM(자식 그룹 graceful) → grace 대기 → 세션 프로세스그룹 SIGTERM 잔여정리(detach 된 `next dev` 워커 포함). 초기 구현은 killpg-우선이라 next 워커가 :3000 orphan → honcho-우선 + 그룹 sweep 으로 교정 |
| **status/logs** | `make mpm-status`(pid 생존), `make mpm-logs`(tail). `.mpm/` gitignore |

## E2E 로그

```
make mpm ENV=local → mpm started (pid …, groups=all)
health 폴링: all 7 up at tick 2
  8003/8001/8002/8004 /health OK · 3001 /health OK · 3002 /api/health OK · 3000 OK
bff /api/dashboard/005930 → 실데이터 200 (price·indicators·decision)
bff /api/candles/005930?days=5 → OHLCV bars 200
make mpm-stop → mpm stopped
포트 재확인: ALL PORTS FREE (orphan 0)
```

## 픽스 이력

1. **bff `process` 미해결** → @types/node devDep + tsconfig types. tsc clean.
2. **offline install 이 node_modules purge** → 네트워크 pnpm install(승인) 복구. (교훈: 부유 버전 범위 +
   미스토어 전이의존성 → `--offline` 위험. frozen-lockfile 또는 온라인 설치 권장.)
3. **mpm-stop 후 :3000 orphan** (next dev 워커가 프로세스그룹 escape) → stop 로직을 honcho-PID-우선
   graceful + grace 대기 + 그룹 SIGTERM sweep 으로 교정. 재시험 ALL PORTS FREE 확인.

## 검증 커맨드
```bash
cd web/apps/bff && pnpm exec tsc --noEmit          # exit 0
cd web && pnpm -r test                             # 26
cd tools/mpm && <analysis venv>/bin/python -m pytest test_mpm.py -q   # 17
make mpm ENV=local && sleep 15 && curl -sf localhost:3002/api/health && make mpm-stop
```
