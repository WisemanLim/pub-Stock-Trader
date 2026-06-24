# stock-trader — 루트 Makefile (Python + Rust + Node 통합)
.PHONY: up up-app down dev-analysis dev-rag dev-ingest dev-agents dev-risk dev-tui dev-web \
        local-all local-stop local-logs local-status \
        prod-all prod-stop prod-logs prod-status prod-build \
        dev-all mpm mpm-stop mpm-status mpm-logs mpm-check sync db-reset test-py test-rust test-web test build deploy \
        setup setup-local setup-prod

# 환경 선택: make <target> ENV=local|dev|staging|prod  (기본 local)
ENV ?= local
MPM_DIR := .mpm

# ── 인프라 (postgres+pgvector, redis) ───────────────────────────────────────────
# ENV 를 compose 로 전달 → env_file 가 .env.$(ENV) 선택. local 도 동일 인프라 사용.
up:
	ENV=$(ENV) docker compose up -d
# 전체 앱 스택(app 프로파일)까지 컨테이너로 기동
up-app:
	ENV=$(ENV) docker compose --profile app up -d
down:
	ENV=$(ENV) docker compose --profile app down --remove-orphans

# ── 환경 초기화 (의존성 재설치 · 컨테이너 준비) ──────────────────────────────────
# make setup              # ENV=local (기본) — web/node_modules·services/*/.venv 삭제·재설치 + uv sync
# make setup-local        # local 단축키
# make setup-prod         # prod 단축키  — 이미지 빌드만
setup: setup-$(ENV)

setup-local: local-stop
	@echo "── local 환경 초기화 ──────────────────────────────────────"
	rm -rf web/node_modules web/apps/*/node_modules web/packages/*/node_modules
	rm -rf services/*/.venv
	cd web && pnpm install
	cd services/analysis && uv sync --dev
	cd services/rag      && uv sync --dev
	cd services/ingest   && uv sync --dev
	cd services/agents   && uv sync --dev
	@echo "완료 → make local-all"

setup-prod:
	@echo "── prod 환경 초기화 ───────────────────────────────────────"
	ENV=prod docker compose --profile app build
	@echo "완료 → make prod-all"

# ── 의존성 일괄 동기화 ───────────────────────────────────────────────────────────
sync:
	cd services/analysis && uv sync --dev
	cd services/rag      && uv sync --dev
	cd services/ingest   && uv sync --dev
	cd services/agents   && uv sync --dev
	cd web && pnpm install

# ── DB 초기화 (사용자·분석 데이터 전체 삭제) ──────────────────────────────────────
# ⚠  이 명령은 모든 데이터를 영구 삭제합니다. 복구 불가.
# 대시보드 auth = SQLite(node:sqlite, 모든 환경). PostgreSQL = 분석 서비스 전용.
# - ENV=local           : auth.db 로컬 파일 삭제
# - ENV=dev|staging|prod: dashboard-data 볼륨(auth.db) + pgdata 볼륨(PostgreSQL) 삭제
db-reset:
ifeq ($(ENV),local)
	rm -f web/apps/dashboard/data/auth.db
	@echo "auth.db 삭제 완료 (local·SQLite) — 다음 기동 시 스키마 자동 재생성"
else
	@echo "⚠  DB 전체 초기화 (ENV=$(ENV)) — 컨테이너 중지 후 볼륨 삭제..."
	@ENV=$(ENV) docker compose --profile app down --remove-orphans 2>/dev/null || true
	@ENV=$(ENV) docker compose down --remove-orphans 2>/dev/null || true
	@docker volume rm stock-trader_dashboard-data 2>/dev/null \
	  && echo "  ✓ dashboard-data 삭제 (auth.db)" \
	  || echo "  · dashboard-data 없음 (이미 삭제됨)"
	@docker volume rm stock-trader_pgdata 2>/dev/null \
	  && echo "  ✓ pgdata 삭제 (PostgreSQL — paper_fills·pgvector·OHLCV 포함)" \
	  || echo "  · pgdata 없음 (이미 삭제됨)"
	@echo "재기동: make up-app ENV=$(ENV)"
endif

# ── Python 서비스 직접 실행 (직접실행 우선, .env.$(ENV) 자동 로드) ────────────────
# pydantic-settings 는 각 서비스 CWD 의 .env.local 을 읽음. ENV!=local 시 해당 파일 지정.
dev-analysis:
	cd services/analysis && APP_ENV=$(ENV) uv run uvicorn app.main:app --reload --port 8001
dev-rag:
	cd services/rag && APP_ENV=$(ENV) uv run uvicorn app.main:app --reload --port 8002
dev-ingest:
	cd services/ingest && APP_ENV=$(ENV) uv run uvicorn app.main:app --reload --port 8003
dev-agents:
	cd services/agents && APP_ENV=$(ENV) uv run uvicorn app.main:app --reload --port 8004

# ── Rust 서비스 직접 실행 (.env.$(ENV) 를 환경변수로 로드 후 실행) ────────────────
dev-risk:
	set -a; . ./.env.$(ENV); set +a; cd core/risk-engine && cargo run
dev-tui:
	set -a; . ./.env.$(ENV); set +a; cd apps/tui && cargo run

# ── Web (Next.js dashboard + NestJS BFF) ────────────────────────────────────────
dev-web:
	set -a; . ./.env.$(ENV); set +a; cd web && pnpm -r dev

# ── 로컬 전체 기동 (호스트 직접 실행, ENV=local) ────────────────────────────────────
# 터미널 1개로 전 서비스(py×4 + rust×1 + web×1) 백그라운드 기동.
# ※ dev-all / mpm 과 동시에 실행하면 포트 충돌 → local-all 만 사용.
#   make local-all   # 전 서비스 백그라운드 기동 (기존 mpm 자동 중지 후 재시작)
#   make local-stop  # 전 서비스 중지
#   make local-logs  # 실시간 로그
#   make local-status # 프로세스 상태 확인
local-all: local-stop
	python3 tools/mpm/mpm.py up --env $(ENV) $(foreach g,$(GROUP),--group $(g))
local-stop:
	python3 tools/mpm/mpm.py stop 2>/dev/null || true
local-logs:
	tail -f $(MPM_DIR)/mpm.log
local-status:
	python3 tools/mpm/mpm.py status

# ── 프로덕션 전체 기동 (Docker Compose, ENV=prod) ────────────────────────────────────
# AUTH_JWT_SECRET 을 쉘에서 export 한 뒤 실행:
#   export AUTH_JWT_SECRET=$(openssl rand -base64 32)
#   make prod-all    # 인프라 + 전체 앱 컨테이너 기동
#   make prod-stop   # 전 컨테이너 중지
#   make prod-logs   # 통합 로그 tail
#   make prod-status # 컨테이너 상태
#   make prod-build  # 이미지 빌드
prod-all:
	ENV=prod docker compose up -d
	ENV=prod docker compose --profile app up -d
prod-stop:
	ENV=prod docker compose --profile app down --remove-orphans
prod-logs:
	ENV=prod docker compose --profile app logs -f
prod-status:
	ENV=prod docker compose --profile app ps
prod-build:
	ENV=prod docker compose --profile app build

# ── 포그라운드 전체 기동 (터미널 점유, 색상 로그) ────────────────────────────────────
# ※ local-all(백그라운드)과 동시에 실행 금지 — 포트 충돌.
#   make dev-all            # 전 서비스 포그라운드 (Ctrl-C 로 전체 종료)
dev-all:
	uvx --from honcho honcho -f Procfile.dev start

# ── MPM 저수준 명령 (local-all/local-stop 권장; 직접 조작 시 사용) ─────────────────
mpm:
	python3 tools/mpm/mpm.py up --env $(ENV) $(foreach g,$(GROUP),--group $(g))
mpm-stop:
	python3 tools/mpm/mpm.py stop
mpm-status:
	python3 tools/mpm/mpm.py status
mpm-logs:
	tail -f $(MPM_DIR)/mpm.log
mpm-check:
	python3 tools/mpm/mpm.py --check --env $(ENV) $(foreach g,$(GROUP),--group $(g))

# ── 시험 ────────────────────────────────────────────────────────────────────────
test-py:
	cd services/analysis && uv run pytest
	cd services/rag     && uv run pytest
	cd services/ingest  && uv run pytest
	cd services/agents  && uv run pytest
test-rust:
	cargo test --workspace
test-web:
	cd web && pnpm -r test
test: test-py test-rust test-web

# ── 컨테이너 빌드 (dev 이상) ─────────────────────────────────────────────────────
build:
	ENV=$(ENV) docker compose --profile app build

# ── 배포 ─────────────────────────────────────────────────────────────────────────
deploy:
	helm upgrade --install stock-trader ./deploy/helm
