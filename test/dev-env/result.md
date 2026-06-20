# dev-env 환경 검증 결과

**판정: PASS** (Docker 기동 후 갱신 — 최초 PARTIAL → FULL)
**일시: 2026-06-06**

## 결과 표

| # | 항목 | 결과 | 버전/비고 |
|---|------|------|-----------|
| 1 | Python 버전 | ✅ PASS | 3.14.5 (Homebrew) |
| 2 | uv 설치 | ✅ PASS | (sync 성공) |
| 3 | uv venv Python | ✅ PASS | 3.13.12 (venv) |
| 4 | Node.js 버전 | ✅ PASS | v26.0.0 |
| 5 | pnpm 버전 | ✅ PASS | 10.33.0 |
| 6 | Rust/cargo 버전 | ✅ PASS | 1.95.0 (~/.cargo/bin, PATH 외부 설정 필요) |
| 7 | Docker 데몬 | ✅ PASS | Docker Desktop 기동 후 `make up` 정상 |
| 8 | docker compose | ✅ PASS | postgres(pgvector:pg17)+redis 기동, pgvector 0.8.2, redis PONG |
| 9 | make 동작 | ✅ PASS | GNU Make (Makefile 확인) |
| 10 | finance-datareader | ✅ PASS | 0.9.202 (finance-datareader) |
| 11 | FastAPI 임포트 | ✅ PASS | 0.136.3 |
| 12 | MCP cli | ✅ PASS | mcp 1.27.2 |

## 규제 체크

| 항목 | 결과 |
|------|------|
| `.env.*` gitignore 포함 | ✅ PASS |
| `.env.example` placeholder 전용 | ✅ PASS (`<vault-or-keychain>` 형식) |

## 이슈 & 조치

1. **cargo PATH**: `~/.cargo/bin` 이 기본 PATH 에 없음. `~/.zshrc` 또는 `.bashrc` 에 `export PATH=$HOME/.cargo/bin:$PATH` 추가 필요. (cargo test 시 해당 export 로 정상 실행 확인.)
2. **Docker Desktop**: 초기 미실행 → `open -a Docker` 로 기동, 약 30초 후 `make up` 정상. postgres+redis healthy, pgvector 확장 동작 확인 완료.
3. **docker-compose.yml YAML 버그**: `env_file: [.env.${ENV:-dev}]` 의 `:-` 가 flow sequence 파싱 오류 유발 → 값 인용으로 수정(impl/2 참조).
