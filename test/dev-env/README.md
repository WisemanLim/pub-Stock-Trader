# test/dev-env — 표준 환경 검증 시나리오

> wise-dev-standard test-runner 기준: 구현 시작 전 1회 실행.

## 사전 조건

- `uv` 설치: `uv --version`
- `cargo` 설치: `cargo --version`
- `pnpm` 설치: `pnpm --version`
- Docker + docker compose: `docker compose version`

## 체크리스트

### 인프라
- [ ] `make up` — postgres+pgvector(:5432), redis(:6379) 기동 확인
- [ ] `docker compose ps` — 컨테이너 healthy 상태 확인

### Python 서비스 (직접실행)
- [ ] `make dev-analysis` → `curl http://localhost:8001/health` → `{"status":"ok"}`
- [ ] `make dev-rag`      → `curl http://localhost:8002/health` → `{"status":"ok"}`
- [ ] `make dev-ingest`   → `curl http://localhost:8003/health` → `{"status":"ok"}`
- [ ] `make dev-agents`   → `curl http://localhost:8004/health` → `{"status":"ok"}`

### Rust 서비스
- [ ] `make dev-risk` → `curl http://localhost:3001/health` → `{"status":"ok","service":"risk-engine"}`
- [ ] 응답 시간 목표: **10ms 이내** (NFR F4)

### Web
- [ ] `make dev-web` — Next.js dashboard(:3000) + NestJS bff(:3002) 기동 확인

### 전체 시험
- [ ] `make test` — pytest + cargo test + vitest 전부 통과

## 결과

| 항목 | 상태 | 비고 |
|---|---|---|
| postgres+pgvector 기동 | ⬜ | |
| analysis /health | ⬜ | |
| rag /health | ⬜ | |
| ingest /health | ⬜ | |
| agents /health | ⬜ | |
| risk-engine /health (≤10ms) | ⬜ | |
| web dashboard 기동 | ⬜ | |
| make test 전체 통과 | ⬜ | |

---
실행일: ____-__-__  담당: ___________
