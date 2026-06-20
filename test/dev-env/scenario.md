# dev-env 환경 검증 시나리오

## 목적
로컬 개발 환경(런타임·패키지 매니저·빌드 도구) 최초 1회 검증.

## 검증 항목

| # | 항목 | 명령 | 기대 결과 |
|---|------|------|-----------|
| 1 | Python 버전 | `python3 --version` | 3.12+ |
| 2 | uv 설치 | `uv --version` | 0.4+ |
| 3 | uv venv Python | `uv run python --version` (services/ingest) | 3.12+ |
| 4 | Node.js 버전 | `node --version` | 20 LTS+ |
| 5 | pnpm 버전 | `pnpm --version` | 9+ |
| 6 | Rust/cargo 버전 | `cargo --version` | 1.80+ |
| 7 | Docker 데몬 | `docker info` | 정상 응답 |
| 8 | docker compose | `docker compose version` | v2.x |
| 9 | make 동작 | `make --version` | GNU Make |
| 10 | finance-datareader | `uv run python -c "import FinanceDataReader"` | 오류 없음 |
| 11 | FastAPI 임포트 | `uv run python -c "import fastapi"` | 오류 없음 |
| 12 | MCP cli | `uv run python -c "from mcp.server.fastmcp import FastMCP"` | 오류 없음 |

## 금융 규제 체크 (COMPLIANCE.md §보안)
- `.env.*` 파일이 `.gitignore` 에 포함되어 있는지 확인.
- `.env.example` 에 실 키 기재 여부 확인(placeholder `<vault>` 형식인지).
