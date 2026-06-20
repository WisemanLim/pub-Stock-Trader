# 개발환경 표준 (Wise Dev Standard)

> 이 파일은 Claude Code / Cursor / Antigravity 가 공통으로 읽는 프로젝트 표준이다.
> AI 코딩 도구는 코드·CI·인프라 생성 시 아래 표준을 기본값으로 준수한다.

## 현재 프로젝트 기본 스택 (Stock Trader AI Platform)

- **profile**: `python-fastapi` (+ `rust-axum` 코어, `node-next-nest` 웹) · **domain**: `finance` (KSIC K)
- **언어/매니저**: Python(uv) · Rust(cargo) · Node/TS(pnpm)
- **서비스** (`services/*` FastAPI, `core/risk-engine` Rust/Axum, `apps/tui` ratatui, `web/` Next.js+NestJS):
  - ingest :8003 (시세·호가창·뉴스·FastMCP·브로커 WS)
  - analysis :8001 (기술지표·LSTM/Transformer·강화학습 백테스팅·거시/뉴스 채널)
  - rag :8002 (Quant RAG·pgvector·환각차단)
  - agents :8004 (멀티에이전트·Telegram/Discord 알림)
  - risk-engine :3001 (Stop-Loss·Trailing·일일한도·가상체결·위험지표)
- **DB**: PostgreSQL 17(pgvector) + Redis. local=sqlite.
- **실행**: `make up`(인프라) · `make dev-*`(직접실행) · `make test`(pytest+cargo+vitest).
- **시험**: `test/dev-env/`(1회) + `test/impl/<Nth>/`(구현마다). 현재 17차 진행, 269 통과.
- **⚠️ 전 거래는 가상(시뮬레이션) 체결** — 실 브로커 송출 없음. 원장 append-only.

## 우선순위 언어
Node/TypeScript · Python · Rust · Go · C/C++ (동점이면 이 순서).
- Node/TS: 프론트, BFF/API Gateway · Python: 데이터/ML/분석 API, RAG(uv+FastAPI)
- Go: 고처리량 코어 · Rust: 메모리안전+극한성능(리스크엔진·TUI) · C/C++: 네이티브

## 패키지 매니저
- Python: **uv** (pyproject.toml + uv.lock) · Node: **pnpm**(monorepo workspaces) · Rust: cargo
- 금지/지양: forever(레거시), yarn/bun 승인제

## 레이어 표준
- Frontend: Next.js(App Router)+React+TS+Tailwind, Vitest+Playwright
- Backend: NestJS / FastAPI / Gin / Axum (ORM: Prisma/SQLAlchemy/GORM/SQLx)
- Database: PostgreSQL(신규 기본)+Redis, local/test 만 SQLite. 벡터=pgvector.
- Ops: GitHub Actions, Docker+Compose, K8s+Helm, Argo CD/Flux, SonarQube+Sentry

## 환경 (local / prod)
| 환경 | DB | compose | 핵심 |
|---|---|---|---|
| local | SQLite | 보통 X | 빠른 반복, 외부 의존 최소 |
| prod | PostgreSQL | O (K8s) | Docker Compose / Helm + GitOps |

`make local-all` (호스트 직접) · `make prod-all` (Docker Compose) 로 환경 선택.

## 실행 방식
- 직접: `make dev-ingest`(uvicorn --reload) / `make dev-risk`(cargo run) / `pnpm -r dev`
- 컨테이너: `make up`(인프라) · `make up-app`(전체 프로파일)
- 프로덕션: K8s + Helm. 공통 진입점 Makefile.

## 시험 / Testing (표준)
프로젝트 루트 `test/` 에 저장.
- `test/dev-env/` — 표준 환경 검증(1회): deps·compose up·DB·health·`make test`.
- `test/impl/<Nth>/` — 구현마다 차수 디렉터리. `scenario.md`+`result.md`(+logs).
- 사이클: 시나리오 작성 → 시험 → 오류 시 수정·재시험 → 결과 작성.
- 러너: pytest(Python·torch는 메인스레드 직접 호출로 segfault 회피) · cargo test(Rust) · vitest(Web).
- 모델·RL 시드 고정으로 결정적(감사 가능). 외부 의존(FDR·뉴스·DB)은 mock 또는 중립 폴백.

## CI/CD
단일 파이프라인 build → test → scan → deploy. K8s 배포는 GitOps(Argo CD/Flux).

## 코드 생성 정책 (AI 도구용)
1. 외부 트래픽/SEO 웹 → Next.js. 내부 툴/콘솔 → Vite SPA / ratatui TUI.
2. BFF/API Gateway → NestJS. 데이터/ML API → FastAPI. 고성능·저지연 코어 → Rust(Axum).
3. 신규 DB → PostgreSQL + Redis. 로컬/테스트만 SQLite. 벡터검색 pgvector.
4. CI 는 GitHub Actions, 쿠버네티스 배포는 Helm + GitOps.
5. 시크릿은 코드/`.env` 에 하드코딩 금지 — Vault/OS Keychain 주입.

## 업종/업태(도메인) 표준 — finance (KSIC K)

> COMPLIANCE.md 와 함께 준수. 규제 적합성은 법무·보안 검토 필수.

**한국 규제(1순위 근거):**
- 전자금융거래법 — 무권한거래 책임 → 인증·로깅·책임추적 설계
- 전자금융감독규정(2025-02-05) — 망분리 위험기반 예외·SaaS 기준·가명정보 R&D 허용
- 신용정보법 — 개인신용정보 가명/익명·비프로드 반출 통제
- 개인정보보호법(PIPA) · ISMS-P(2025 강화, 위반 시 인증취소)
- 마이데이터 2.0(2025-06-19) · 재해복구센터 DR/BCP(2026 단계적) — F4 Fail-Safe 직결

**국제 기준:** PCI-DSS 4.0.1(CDE 전구간 MFA·토큰화) · SOC 2 Type II · PSD2 SCA/RBA · ISO 20022 · DORA/PQC

**데이터 등급:**
- 🔴 규제대상: 개인신용정보·결제/카드(CHD/SAD)·인증/API키 → 비프로드 반입 금지·HSM/KMS·토큰화
- 🟠 민감: PII·계좌번호 → PIPA·암호화
- 🟡 제한: 가명/익명정보 → R&D 가능·재식별 방지
- 🟢 무결성: 거래원장·감사로그·체결기록 → append-only·변조방지(가상체결 원장 포함)
- ⚪ 일반: 기술지표·뉴스·공시·가격

**인프라 델타:** CDE 망분리 · 멱등키(Idempotency-Key)+정산 대사 · Transactional Outbox · HSM/KMS · 실시간 사기탐지(RBA·SCA) · DR/BCP

**개발환경 필수:**
1. 비프로덕션(`.env.local`)에 실 개인신용정보·결제데이터 절대 반입 금지 — 합성 데이터만.
2. 증권사 API Key/Secret·LLM 키 → OS Keychain / Vault. 파일 기재 금지.
3. 코드→배포 불변 감사추적(ISMS-P 증적).

**추가 시험(domain testing_additions):** 멱등 결제(중복 1건) · 정산 대사(레일 vs 원장) · 보상 트랜잭션 · CDE MFA·토큰화. 본 프로젝트 적용: 가상체결 멱등·append-only 원장·환각차단(RAG)·부분장애 격리(degrade/폴백).

## 도메인(연구/RAG) 확장 시
출처 병기 · 권한(ACL) 필터 · 비식별화 · 감사로그 · 재현성(모델/청커/프롬프트 버전 고정) · 하이브리드 검색(BM25+벡터). 고위험 응답은 human-in-the-loop. (rag 서비스: 근거 없으면 답변 거부 = 환각차단.)

---
_생성: wise-dev-standard 플러그인. 갱신은 `/wise-dev-standard:standardize`._
