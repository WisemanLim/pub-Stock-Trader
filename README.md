[English](README.en.md) | **한국어**

# Stock Trader AI Platform

> 금융 도메인(KSIC K) 실시간 주식 트레이딩 AI 플랫폼.
> 규제 준수: 전자금융감독규정·ISMS-P·PCI-DSS 4.0.1 → [COMPLIANCE.md](COMPLIANCE.md)

## 개요

profile: `python-fastapi` (+ `rust-axum` 코어, `node-next-nest` 웹) · domain: `finance`

| 문서             | 링크                          |
| ---------------- | ----------------------------- |
| 규제 가이드      | [COMPLIANCE.md](COMPLIANCE.md) |
| 환경 변수 템플릿 | [.env.example](.env.example)   |

![Stock Trader AI Platform Demo](Stock-Trader.gif)

## 구현 현황 (PRD 매핑)

| 기능                     | 서비스               | 상태 | 비고                                                                                                                                                                                                                                   |
| ------------------------ | -------------------- | ---- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| F1.1 시세·OHLCV·종목     | ingest               | ✅   | FinanceDataReader                                                                                                                                                                                                                      |
| F1.2 호가창              | ingest               | ✅   | 가격기반 시뮬레이션                                                                                                                                                                                                                    |
| F1.2 브로커 WS 피드      | ingest               | ✅   | 실 WS 연동 / random-walk 시뮬 폴백                                                                                                                                                                                                     |
| F1.2 적응형 흐름제어     | ingest               | ✅   | **AIMD 처리율 + 우선순위 큐 + 백프레셔** — `SubscriptionManager` 토큰버킷에 통합(옵트인)                                                                                                                                               |
| F1.5 KRX OPEN API 수집기 | ingest               | ✅   | OTP→데이터 2단계, OHLCV+투자자수급, API키 미설정 시 폴백                                                                                                                                                                               |
| F1.3 뉴스 RSS            | ingest               | ✅   | feedparser                                                                                                                                                                                                                             |
| F1.4 FastMCP             | ingest               | ✅   | Claude/Gemini 연동                                                                                                                                                                                                                     |
| F2.1 기술지표            | analysis             | ✅   | RSI·MACD·Bollinger·EMA·SMA·ATR                                                                                                                                                                                                         |
| F2.2 예측                | analysis             | ✅   | 멀티변량(거시 합성 17종 + **erc_quest_adaptive(적응격자 QuEST)·erc_factor(MP 팩터/노이즈 분리)** + MP 적합도검정 + FinBERT/KR-FinBERT)                                                                                                 |
| F2.3 스크리너            | analysis             | ✅   | RSI·거래량 필터                                                                                                                                                                                                                        |
| F3.1 멀티에이전트        | agents               | ✅   | Scraper·Analyst·Portfolio·Decision                                                                                                                                                                                                     |
| F3.3 자가교정 루프       | agents               | ✅   | **전략 드리프트 감시(churn·저신뢰·비중위반) + HOLD 강등·비중 클램프**                                                                                                                                                                  |
| F3.2 Quant RAG           | rag                  | ✅   | 하이브리드 검색·환각차단 + pgvector 영속화                                                                                                                                                                                             |
| F4 리스크 엔진           | risk-engine          | ✅   | Stop-Loss·Trailing·일일한도·Fail-Safe                                                                                                                                                                                                  |
| F5 백테스팅              | analysis             | ✅   | 다전략 + RL(…·DPG **reinforce/a2c/ppo·GAE**) + **영속 워커풀·공유메모리(persistent)**                                                                                                                                                  |
| F5 가상체결              | risk-engine          | ✅   | 다종목·롤링·5요인·full VAR(p)·YW + companion 복소 고유값 QR(Schur) 반경 사영 + **계정 다중화(account별 격리 원장)**                                                                                                                    |
| F6.1 스캘퍼 TUI          | apps/tui             | ✅   | ratatui 호가창·P&L                                                                                                                                                                                                                     |
| F6.2 웹 대시보드         | web                  | ✅   | Next.js + NestJS BFF + **4분면 캔들 차트(5분봉·시간대별·요일별·일봉)** + **다크/라이트 테마 토글·툴팁** + **TopBar 종목코드+기업명 표시·localStorage 영속** + 서브페이지 자동조회(리스크·백테스팅·에이전트)                            |
| F7 시뮬레이션 매수/매도  | web/risk             | ✅   | 대시보드 매수▲/매도▼ 패널(SimulationPanel) → BFF POST /api/paper/execute → risk-engine 가상체결 원장 · **예수금 추적(초기 설정액, 매수차감/매도가산)** → 포트폴리오 현재가·종목명·손익·비중 BFF 보강                                  |
| F8 사용자 인증           | web                  | ✅   | 회원가입/로그인(bcryptjs+jose JWT+TOTP otplib), **회원가입 시 예수금 직접 지정**, **Sidebar 롤업 마이페이지**(비밀번호·예수금·TOTP), AuthGuard 라우트 보호, SQLite(`node:sqlite` Node 24 내장, `globalThis` HMR 싱글톤)               |
| F6.3 알림                | agents               | ✅   | Telegram/Discord webhook                                                                                                                                                                                                               |
| F6.3 양방향 제어         | agents + risk-engine | ✅   | **봇 중지(halt)/긴급청산 원격 제어 + 인바운드 명령(시크릿 인증)**                                                                                                                                                                      |
| F9 서비스 상태           | web/bff              | ✅   | Sidebar 실시간 헬스체크(30초 폴링) · BFF `/api/services/health` 병렬 체크                                                                                                                                                              |
| F10 Docker prod          | web                  | ✅   | BFF·Dashboard 멀티스테이지 Dockerfile · Next.js standalone · **`make prod-all`** / `make prod-stop`                                                                                                                                    |

## 아키텍처 / 서비스 역할

```
Stock-Trader/
├── services/
│   ├── ingest/     F1 시세·호가창·뉴스·FastMCP·AIMD흐름제어  :8003  Python/FastAPI
│   ├── analysis/   F2 기술지표·예측·스크리너·RL(영속풀)        :8001  Python/FastAPI
│   ├── rag/        F3.2 Quant RAG                          :8002  Python/FastAPI
│   └── agents/     F3.1 멀티에이전트·F3.3 자가교정·F6.3 제어   :8004  Python/FastAPI
├── core/risk-engine/  F4 Stop-Loss/Trailing·F6.3 halt/청산  :3001  Rust/Axum
├── Procfile.dev       MPM 정적 오케스트레이션(make dev-all)
├── tools/mpm/         MPM Procfile 생성기(레지스트리·ENV·그룹, make mpm)
├── apps/tui/          F6.1 스캘퍼 콘솔                  Rust/ratatui
└── web/
    ├── apps/dashboard  F6.2 대시보드              :3000  Next.js 15
    └── apps/bff        BFF 집계 게이트웨이         :3002  NestJS 11
```

인프라: PostgreSQL 17 (pgvector 0.8.2) + Redis 7.4

## 사전 요구사항

| 도구           | 버전(검증)           | 확인                |
| -------------- | -------------------- | ------------------- |
| Python         | 3.12+ (venv 3.13.12) | `python3 --version` |
| uv             | 0.4+                 | `uv --version`      |
| Node.js        | 20 LTS+ (v26)        | `node --version`    |
| pnpm           | 9+ (10.33)           | `pnpm --version`    |
| Rust/cargo     | 1.80+ (1.95)         | `cargo --version`   |
| Docker Desktop | 최신                 | `docker info`       |

> **cargo PATH**: `export PATH=$HOME/.cargo/bin:$PATH` — `~/.zshrc` 에 추가

## 환경 설정

```bash
cp .env.example .env.local   # 루트 + 각 서비스 디렉터리
```

| 파일         | 용도                                        |
| ------------ | ------------------------------------------- |
| `.env.local` | 로컬 직접 실행 (SQLite, Redis 선택)         |
| `.env.prod`  | 키 목록만 — Vault/K8s External Secrets 주입 |

> **⚠️ 실 증권사 API Key·Secret → OS Keychain 또는 Vault. 파일 기재 절대 금지.**
> 비-프로덕션 데이터는 합성 데이터만 사용 (COMPLIANCE.md).

### AUTH_JWT_SECRET 설정 방법

대시보드(F8 사용자 인증)는 JWT 서명에 `AUTH_JWT_SECRET`(32바이트 이상 랜덤값)을 필요로 한다.

**발급:**
```bash
openssl rand -base64 32
```

| 환경 | 방법 | 비고 |
|------|------|------|
| `local` | `.env.local` 에 직접 기재 | 개발용 임시값 허용 |
| `prod` | 쉘 `export` 후 make 실행 (K8s: Vault 자동 주입) | 파일 기재 절대 금지 |

> **Docker Compose env_file 주의:** `.env.prod` 의 `${AUTH_JWT_SECRET}` 는 쉘 변수로 **확장되지 않는다**. compose 실행 전 반드시 쉘에서 `export` 로 설정해야 한다.

```bash
# prod — Docker Compose 실행 전 쉘에서 설정
export AUTH_JWT_SECRET=$(openssl rand -base64 32)
make up ENV=prod

# macOS Keychain 활용 (장기 보관)
security add-generic-password -a stock-trader -s AUTH_JWT_SECRET \
  -w "$(openssl rand -base64 32)"
export AUTH_JWT_SECRET=$(security find-generic-password \
  -a stock-trader -s AUTH_JWT_SECRET -w)
make up ENV=prod
```

각 서비스는 자체 CWD 의 `.env.local` 을 pydantic-settings 로 로드:

```
services/ingest/.env.local, services/analysis/.env.local, ...
```

## 실행 방법

### A) docker compose (멀티서비스)

```bash
# ── 환경 초기화 (첫 설치 · node_modules·.venv 재설치 시) ────────
make setup               # ENV=local (기본) — web/node_modules·services/*/.venv 삭제·재설치 + uv sync
make setup-local         # local 단축키 (서비스 중지 → 재설치 → make local-all 로 기동)
make setup-prod          # prod  단축키  — 이미지 빌드만

make up                  # 인프라만 (postgres+pgvector, redis). ENV=local
make up-app              # 전체 앱 스택(app 프로파일)까지 컨테이너 기동
make build               # docker compose --profile app build
make sync                # 전 서비스 의존성 동기화 (uv sync + pnpm install)
make dev-ingest          # 개별 서비스 (uvicorn --reload, 볼륨마운트)
make dev-analysis / dev-rag / dev-agents / dev-risk / dev-tui / dev-web
make local-all           # ENV=local 전 서비스 백그라운드 기동 (권장, 기존 프로세스 자동 중지 후 재시작)
make local-stop          # 전 서비스 중지
make local-logs          # 통합 로그 tail
make local-status        # 프로세스 상태
make dev-all             # 포그라운드 기동 (터미널 점유, Ctrl-C 전체 종료)
make down                # 전체 중단
```

### MPM(멀티프로세스 매니저) — `make local-all` (권장)

6 프로세스(ingest·analysis·rag·agents·risk·web)를 **터미널 1개**로 일괄 기동·관리. `uvx` 로 honcho 임시 실행 → **별도 설치 불필요**.

> ⚠️ `make local-all`(백그라운드)과 `make dev-all`(포그라운드)을 **동시에 실행하면 포트 충돌**로 서비스가 강제 종료됩니다. 둘 중 하나만 사용하세요.

```bash
# ── 권장: 백그라운드 일괄 기동 ─────────────────────────────
make local-all                    # ENV=local 전 서비스 백그라운드 기동 (기존 프로세스 자동 중지)
make local-stop                   # 전 서비스 중지
make local-logs                   # 통합 로그 tail (.mpm/mpm.log)
make local-status                 # 프로세스 상태(pid)

# ── 포그라운드 (터미널 점유, 색상 로그) ───────────────────────
make dev-all                      # Ctrl-C 로 전체 종료

# ── 저수준 MPM 명령 ────────────────────────────────────────
make mpm ENV=local GROUP="py rust"  # python+rust 그룹만
make mpm-check ENV=local GROUP=py   # 생성물 검증(exit code)
```

> **tools/mpm**: 서비스 레지스트리(`SERVICES`) 단일 소스에서 ENV·그룹별 honcho Procfile 을 결정적 생성하고, 전 프로세스를 **백그라운드(detached)** 로 일괄 기동·중지·상태조회한다. `make mpm` = `mpm.py up`(Popen `start_new_session` + `.mpm/{Procfile.gen,mpm.pid,mpm.log}`), `make mpm-stop` = honcho SIGTERM(graceful cascade) + 세션 프로세스그룹 sweep(detach 된 `next dev` 워커까지 정리). 그룹 `py`(ingest·analysis·rag·agents)·`rust`(risk)·`web`. ENV 치환(`APP_ENV`·`.env.{env}`). 표준 라이브러리만(의존 0). 상태 `.mpm/`(gitignore).

> **ENV 전달**: 모든 compose 타겟(`up`/`up-app`/`build`/`down`)이 `ENV=$(ENV)` 를 docker compose 로 넘겨 `.env.$(ENV)` 를 선택. Rust 타겟(`dev-risk`/`dev-tui`)은 `.env.$(ENV)` 를 환경변수로 로드 후 실행.

compose 프로파일:

- 기본(`default`): postgres, redis (`make up`)
- `app`: 모든 서비스 컨테이너 (`make up-app`)

### B) 호스트 직접 실행

```bash
# Python 서비스 (각 디렉터리)
cd services/ingest && uv sync --dev && uv run uvicorn app.main:app --reload --port 8003
cd services/analysis && uv run uvicorn app.main:app --reload --port 8001
cd services/rag && uv run uvicorn app.main:app --reload --port 8002
cd services/agents && uv run uvicorn app.main:app --reload --port 8004

# Rust
export PATH=$HOME/.cargo/bin:$PATH
cargo run -p risk-engine        # :3001
cargo run -p tui                # 스캘퍼 콘솔 (터미널)

# FastMCP 서버 (F1.4)
cd services/ingest && uv run mcp run app/services/mcp_server.py

# Web (pnpm workspace)
cd web && pnpm install
pnpm --filter @stock-trader/bff dev         # :3002
pnpm --filter @stock-trader/dashboard dev   # :3000
```

## 접속·포트 표

| 서비스      | URL                   | 포트 | 프로파일 | API 문서                            |
| ----------- | --------------------- | ---- | -------- | ----------------------------------- |
| ingest      | http://localhost:8003 | 8003 | app      | [/docs](http://localhost:8003/docs) |
| analysis    | http://localhost:8001 | 8001 | app      | [/docs](http://localhost:8001/docs) |
| rag         | http://localhost:8002 | 8002 | app      | [/docs](http://localhost:8002/docs) |
| agents      | http://localhost:8004 | 8004 | app      | [/docs](http://localhost:8004/docs) |
| risk-engine | http://localhost:3001 | 3001 | app      | —                                   |
| bff         | http://localhost:3002 | 3002 | —        | /api/health                         |
| dashboard   | http://localhost:3000 | 3000 | —        | —                                   |
| postgres    | localhost:5432        | 5432 | default  | —                                   |
| redis       | localhost:6379        | 6379 | default  | —                                   |

## 대시보드 페르소나(Persona)

대시보드(`?persona=`) 및 에이전트 분석(`agents/analyze`) 에서 트레이딩 스타일을 선택한다. 페르소나는 리스크 파라미터·포지션 비중 한도·에이전트 결정 임계값에 직접 영향을 준다.

| 페르소나          | URL 값     | 보유 기간       | 특징                                                                             |
| ----------------- | ---------- | --------------- | -------------------------------------------------------------------------------- |
| 스캘퍼 (Scalper)  | `scalper`  | 수 초 ~ 수 분   | 극초단타. 매우 좁은 손절폭, 빠른 진출입, 높은 회전율. 비중 한도 최소(기본 5%).   |
| 데이 (Day Trader) | `day`      | 장중(당일 청산) | 오버나이트 없음. 중간 손절폭, 당일 손익 한도 우선 적용. 비중 한도 중간(기본 8%). |
| 스윙 (Swing)      | `swing`    | 수일 ~ 수주     | 기술적 추세 추종. 표준 손절·트레일링 스탑. 비중 한도 표준(기본 10%). **기본값.** |
| 포지션 (Position) | `position` | 수주 ~ 수개월   | 장기 보유. 넓은 손절폭, 거시 지표·펀더멘털 비중 확대. 비중 한도 최대(기본 15%).  |

> 대시보드 URL 예: `http://localhost:3000/?ticker=005930&persona=scalper`
> 에이전트 API: `POST /agents/analyze` 본문에 `"persona": "day"` 전달.
> 자가교정(`/agents/self_correct`)도 페르소나별 비중 한도 기준으로 드리프트 판정.

## 구현된 API 예시

### F1 ingest

```bash
curl http://localhost:8003/market/price/005930
# {"ticker":"005930","price":73500.0,"change":0.021,"volume":1200000,...}

curl "http://localhost:8003/market/ohlcv/005930?days=30"
curl http://localhost:8003/market/tickers/KRX

curl "http://localhost:8003/orderbook/005930?levels=10"
# {"ticker":"005930","ask_levels":[...],"bid_levels":[...],"spread":50.0,"mid_price":73525.0}

curl http://localhost:8003/news/sources
curl http://localhost:8003/news/reuters-business?limit=10
```

### F2 analysis + F5 백테스팅

```bash
curl "http://localhost:8001/indicators/005930?days=60"
# {"ticker":"005930","rsi":42.5,"macd":{...},"bollinger":{...},"atr":820.0,"signal":"HOLD"}

curl http://localhost:8001/predict/005930                       # 선형회귀(빠름)
curl "http://localhost:8001/predict/005930?model=lstm"          # LSTM
curl "http://localhost:8001/predict/005930?model=transformer"   # Transformer
# {"model":"transformer-v1","weights_source":"checkpoint","horizons":[...]}
curl -X POST "http://localhost:8001/predict/005930/train?arch=transformer"  # 사전학습 → 체크포인트
curl -X POST http://localhost:8001/predict/retrain -H 'content-type: application/json' \
  -d '{"tickers":["005930","000660"],"arch":"lstm","max_age_hours":24}'      # 스케줄 재학습(stale만)

curl -X POST http://localhost:8001/screener/ \
  -H 'content-type: application/json' \
  -d '{"market":"KRX","rsi_max":30,"limit":10}'

# F5 다전략 백테스팅 (sma_cross | rsi_threshold | macd_cross | qlearn)
curl http://localhost:8001/backtest/strategies
curl -X POST http://localhost:8001/backtest/ -H 'content-type: application/json' \
  -d '{"ticker":"005930","days":365,"strategy":"rsi_threshold","params":{"rsi_buy_below":30,"rsi_sell_above":70}}'

# F5 강화학습 백테스팅 — Q-learning(테이블) / DQN(신경망)
curl -X POST http://localhost:8001/backtest/rl  -H 'content-type: application/json' \
  -d '{"ticker":"005930","days":365,"episodes":50}'   # 테이블 Q-learning
curl -X POST http://localhost:8001/backtest/dqn -H 'content-type: application/json' \
  -d '{"ticker":"005930","days":365,"episodes":30}'   # Rainbow급 DQN (Double·Dueling·PER·n-step·Noisy)
curl -X POST http://localhost:8001/backtest/c51 -H 'content-type: application/json' \
  -d '{"ticker":"005930","days":365,"episodes":20}'   # Distributional C51
curl -X POST "http://localhost:8001/backtest/qrdqn?mode=fqf&cvar_alpha=0.25&fqf_state_dependent=true" \
  -H 'content-type: application/json' -d '{"ticker":"005930","days":365,"episodes":15}'  # QR/IQN/FQF + CVaR
curl -X POST "http://localhost:8001/backtest/dpg?mode=ppo&n_rollouts=4&parallel=true&executor=process" -H 'content-type: application/json' \
  -d '{"ticker":"005930","days":365,"episodes":20}'   # DPG(PPO·minibatch·KL) + 멀티프로세스(state_dict 복제) 병렬 롤아웃
# {"strategy":"dpg","mode":"ppo","n_rollouts":4,"parallel":true,"executor":"process","sharpe":..,"num_trades":..}
curl -X POST "http://localhost:8001/backtest/dpg?mode=a2c&n_rollouts=4&parallel=true&executor=persistent" -H 'content-type: application/json' \
  -d '{"ticker":"005930","days":365,"episodes":20}'   # 영속 워커풀(재사용) + 공유메모리(SharedMemory) 텐서
# {"executor":"persistent",...}  — px/rsi 1회 적재·풀 재사용. process·순차와 동일 결과(결정적)
# 영속 풀(MPM): 워커수 BACKTEST_PERSIST_WORKERS env, BrokenProcessPool 자동 재생성, persistent_pool_stats() 조회
```

> RL 병렬 롤아웃 `executor`: `thread`(공유모델) · `process`(에피소드마다 풀 생성, state_dict 복제) · `persistent`(영속 풀 재사용 + `SharedMemory` 로 px/rsi 무복사 매핑 — 풀 재생성 비용 제거). 세 모드 모두 롤아웃별 시드로 순차와 동일 결과.

> 멀티변량 거시 채널: `MACRO_INDICES` 다지표 + `MACRO_COMBINE` 17종(…·erc_lw·erc_cc·erc_oas·erc_nlw·erc_quest·erc_quest_grid·**erc_quest_adaptive**(적응 격자 QuEST, 분위수 노드)·**erc_factor**(MP 상한 λ⁺ 초과=신호 보존·bulk 평탄화 RMT 디노이징)·pca·ipca·ccipca) 합성. 진단: `marchenko_pastur_gof(eigs, c)` = 표본 고유값 vs MP 법칙 KS 거리(신호 검출). 뉴스 센티먼트는 `FINBERT_ENABLED=true` 시 FinBERT(`FINBERT_MODEL`=`ProsusAI/finbert` 또는 KR `snunlp/KR-FinBert-SC`), 아니면 키워드. 소스/모델 장애 시 중립 폴백.

### F3 rag / agents

```bash
curl -X POST http://localhost:8002/rag/ingest -H 'content-type: application/json' \
  -d '{"documents":[{"id":"fed1","content":"Fed held rates at 5.5%","meta":{}}]}'
curl -X POST http://localhost:8002/rag/query -H 'content-type: application/json' \
  -d '{"query":"fed interest rates","k":3}'
# {"answer":"...","sources":[...],"grounded":true}   # 근거 없으면 grounded:false (환각차단)

curl -X POST http://localhost:8004/agents/analyze -H 'content-type: application/json' \
  -d '{"ticker":"005930","persona":"swing"}'
# {"notes":[{"agent":"Scraper",...},...],"decision":{"signal":"BUY","weight":0.27,"confidence":0.8}}

# F3.3 전략 자가교정 — 결정 이력+후보로 드리프트 판정 후 보수적 교정안
curl -X POST http://localhost:8004/agents/self_correct -H 'content-type: application/json' \
  -d '{"persona":"scalper","history":[{"signal":"BUY","confidence":0.8,"weight":0.1}],
       "candidate":{"signal":"BUY","confidence":0.8,"weight":0.5}}'
# {"drift":{"drift":true,"reasons":["weight_breach(...)"],...},
#  "corrected":{"signal":"BUY","weight":0.1,"corrected":true,"corrections":["weight_clamped_to_0.1"]}}
# churn(BUY↔SELL 빈번)·저신뢰 시 → corrected.signal="HOLD"(강등)

# F6.3 알림 (미설정 채널은 false → no-op)
curl -X POST http://localhost:8004/notify/ -H 'content-type: application/json' \
  -d '{"event":"STOP_LOSS","payload":{"ticker":"005930","price":68600}}'
# {"message":"...","telegram":false,"discord":false}

# F6.3 양방향 제어 — 인바운드 명령(시크릿 인증 필수, CONTROL_SECRET 미설정 시 403 전거부)
curl -X POST http://localhost:8004/control/command -H 'content-type: application/json' \
  -d '{"secret":"<control-secret>","text":"/stop"}'        # 봇 긴급 중지(halt)
# {"command":"/stop","result":{"halted":true}}
curl -X POST http://localhost:8004/control/command -H 'content-type: application/json' \
  -d '{"secret":"<control-secret>","text":"/liquidate","prices":{"005930":71000}}'  # 긴급 청산
# {"command":"/liquidate","result":{"liquidated":1,"realized_pnl":..,"halted":true}}
# /resume(재개) · /status(상태). Telegram 웹훅: POST /control/telegram?secret=... (또는 X-Telegram-Bot-Api-Secret-Token 헤더)
```

### F4 risk-engine + 가상체결

```bash
curl -X POST http://localhost:3001/risk/check -H 'content-type: application/json' \
  -d '{"ticker":"005930","entry_price":70000,"current_price":68600,
       "stop_loss_pct":0.02,"daily_loss_limit_pct":0.05,"max_position_pct":0.10}'
# {"ticker":"005930","action":"force_sell","triggered":["stop_loss"],"reason":"Stop-Loss: ..."}

# 가상(시뮬레이션) 체결 — 실거래 아님. 다종목·슬리피지·수수료·append-only 원장
# DATABASE_URL=postgres 면 paper_fills 영속화 + 재시작 하이드레이션
# client_order_id = 멱등키(선택). 동일 키 재전송 시 1회만 체결(원장·DB 중복 방지, COMPLIANCE §4.1)
curl -X POST http://localhost:3001/paper/execute -H 'content-type: application/json' \
  -d '{"ticker":"005930","side":"buy","quantity":10,"price":70000,"client_order_id":"ord-20260607-001"}'
# 재전송(동일 client_order_id) → {"accepted":true,"reason":"중복 주문(멱등키) — 기존 체결 반환",...} (재체결 없음)
curl -X POST http://localhost:3001/paper/execute -H 'content-type: application/json' \
  -d '{"ticker":"000660","side":"buy","quantity":5,"price":120000}'
curl http://localhost:3001/paper/portfolio
# {"positions":[...],"realized_pnl":..,"realized_by_ticker":{"005930":..,"000660":..},"fills":N}

# 계정 다중화 — ?account= 로 격리 원장(미지정=default). DB 영속화는 기본 계정만, 명명 계정은 인메모리.
curl -X POST "http://localhost:3001/paper/execute?account=strat-A" -H 'content-type: application/json' \
  -d '{"ticker":"005930","side":"buy","quantity":10,"price":70000}'
curl "http://localhost:3001/paper/portfolio?account=strat-A"   # {"account":"strat-A","positions":[...],...}
curl http://localhost:3001/paper/accounts                       # {"accounts":["default","strat-A"]}

# mark-to-market — 현재가 입력 → 종목별 미실현 + 손익곡선 점 추가
curl -X POST http://localhost:3001/paper/mark -H 'content-type: application/json' \
  -d '{"005930":75000,"000660":115000}'
# {"realized":..,"unrealized":..,"equity":..,"unrealized_by_ticker":{"005930":..,"000660":..}}
curl http://localhost:3001/paper/equity_curve
# [{"ts":..,"realized":..,"unrealized":..,"equity":..}, ...]   (DATABASE_URL 시 영속·재시작 복원)
curl "http://localhost:3001/paper/equity_agg?period=daily"     # daily|weekly|monthly|quarterly OHLC
# [{"bucket":..,"open":..,"close":..,"high":..,"low":..,"points":N}]
curl -X POST http://localhost:3001/paper/alpha -H 'content-type: application/json' \
  -d '{"initial_capital":10000000,"benchmark":[2400,2450,2500]}'  # 벤치마크 대비 알파
# {"portfolio_return":..,"benchmark_return":..,"alpha":..}
curl -X POST http://localhost:3001/paper/risk_metrics -H 'content-type: application/json' \
  -d '{"initial_capital":10000000,"benchmark":[2400,2440,2420,2480]}'  # beta·IR·TE
curl -X POST http://localhost:3001/paper/risk_rolling -H 'content-type: application/json' \
  -d '{"initial_capital":10000000,"benchmark":[...],"window":20}'      # 롤링 윈도우 지표
curl -X POST http://localhost:3001/paper/factor_regression -H 'content-type: application/json' \
  -d '{"initial_capital":10000000,"factors":[[..mkt..],[..smb..],[..hml..]]}'  # Fama-French OLS
curl -X POST http://localhost:3001/paper/factor_regression_nw -H 'content-type: application/json' \
  -d '{"initial_capital":10000000,"factors":[[..mkt..],[..smb..],[..hml..],[..rmw..],[..cma..]],"lag":4}'
# 5요인 + Newey-West HAC SE: {"alpha":..,"betas":[..×5],"std_errors":[..×6],"lag":4}
curl -X POST http://localhost:3001/paper/factor_regression_nw_auto -H 'content-type: application/json' \
  -d '{"initial_capital":10000000,"factors":[[mkt],[smb],[hml]]}'  # Andrews 자동 대역폭
# {"alpha":..,"betas":[..],"std_errors":[..],"lag_auto":N}
curl -X POST http://localhost:3001/paper/factor_regression_qs -H 'content-type: application/json' \
  -d '{"initial_capital":10000000,"factors":[[mkt],[smb],[hml]],"prewhiten":true,"full_var":true}'  # QS + full VAR(1)
curl -X POST http://localhost:3001/paper/factor_regression_qs_aic -H 'content-type: application/json' \
  -d '{"initial_capital":10000000,"factors":[[mkt],[smb],[hml]],"max_order":5}'  # AIC 대각 AR(p)
curl -X POST http://localhost:3001/paper/factor_regression_qs_var -H 'content-type: application/json' \
  -d '{"initial_capital":10000000,"factors":[[mkt],[smb],[hml]],"max_order":3,"criterion":"bic","stabilize":true,"companion":true}'
# full VAR(p)·BIC/HQ + companion 안정성 사영: {"alpha":..,"std_errors":[..],"var_order":N,"stabilize":true,"companion":true}

# F6.3 긴급 제어 (risk-engine 직접) — agents /control 이 위임하는 엔드포인트
curl -X POST http://localhost:3001/control/halt -H 'content-type: application/json' -d '{"halted":true}'
curl http://localhost:3001/control/status        # {"halted":true,"open_positions":N}
# 계정별 제어: ?account=strat-A (halt·status·liquidate 모두 계정 독립)
# halt=true 면 /paper/execute 신규주문 차단. 청산은 halt 독립(Fail-Safe).
curl -X POST http://localhost:3001/control/liquidate -H 'content-type: application/json' \
  -d '{"prices":{"005930":71000,"000660":121000}}'  # 보유 전종목 시장가 매도 + 자동 halt
# {"liquidated":2,"fills":[...],"realized_pnl":..,"halted":true}  (청산 체결도 append-only 원장 보존)
```

### F1.5 KRX OPEN API

```bash
curl http://localhost:8003/krx/status
# {"configured":false,"note":"KRX_OPEN_API_KEY 환경변수 설정 시 활성화됩니다."}
# API 키 설정 시: KRX_OPEN_API_KEY=<발급키> uv run uvicorn ...

curl "http://localhost:8003/krx/ohlcv/005930?from_date=20260101&to_date=20260131&market=KOSPI"
# {"ticker":"005930","configured":false,"bars":[],"count":0}  (키 미설정)
# 키 설정 시: {"bars":[{"date":"2026-01-01","open":70000,"high":71000,...,"source":"krx_openapi"}],...}

curl "http://localhost:8003/krx/investor-flow/005930"
# {"ticker":"005930","configured":false,"phase":"A_pending","flows":[],"count":0}
# 키 설정 시: {"flows":[{"date":"..","institution":125000,"foreign":-48000,"individual":-77000}],...}
```

> KRX OPEN API 2단계 호출: OTP(`GenerateOTP.jspx`) → 데이터(`jsonSvr.do`). API 키 미설정 시 빈 결과, FinanceDataReader 폴백 유지. API ID: KOSPI=`stk_bydd_trd` / KOSDAQ=`ksq_bydd_trd` / 투자자=`stk_invsr_trd_by_isu`. 호출 간격 최소 0.5s(`KRX_API_RATE_LIMIT`).

### F1.2 브로커 틱 피드 (WebSocket)

```
ws://localhost:8003/market/feed/005930
# BROKER_WS_URL 설정 시 실연동: BROKER_PROTOCOL=generic|kis, 인증(BROKER_API_KEY/SECRET) +
# 하트비트 핑퐁(BROKER_HEARTBEAT_INTERVAL/TIMEOUT) + 지수 백오프 재연결(BROKER_MAX_RETRIES, -1=무한).
# 미설정 시 시뮬레이션.
ws://localhost:8003/market/feed_multi/005930,000660   # 다종목 멀티플렉싱(단일 WS)
```

> **적응형 흐름제어(통합)**: `SubscriptionManager` 옵트인 — `aimd=AIMDRateController(...)` 시 전역 토큰버킷 rate 가 ack 성공=가산증가/구독실패=승법감소(AIMD)로 자동 조절. `command_capacity`/`command_watermark` 시 송신 대기 명령이 우선순위 큐로 관리(해지 우선, 용량초과 시 최저우선 드롭, `command_backpressured()` 신호). 미지정 시 기존 FIFO·고정 rate(하위호환). 순수 흐름제어 단위는 [adaptive_flow.py](services/ingest/app/services/adaptive_flow.py).

### F6.2 BFF 집계 + 실시간 캔들

```bash
curl "http://localhost:3002/api/dashboard/005930?persona=swing"
# {"ticker":"005930","price":{...},"indicators":{...},"decision":{...}}

curl "http://localhost:3002/api/candles/005930?days=30"   # 캔들(OHLCV) — ingest 프록시(days 1~365 클램프)
# {"ticker":"005930","bars":[{"date":..,"open":..,"high":..,"low":..,"close":..,"volume":..}],"count":30}
```

> 대시보드 캔들 차트(`components/CandleChart.tsx`)는 `/api/candles` 로 초기 봉을 받고 `/api/price` 를 5초 폴링해 형성 중 캔들의 close/high/low 를 실시간 갱신(SVG 직접 렌더, 차트 라이브러리 무의존). 기하 변환은 [lib/candles.ts](web/apps/dashboard/lib/candles.ts) 순수 함수로 분리(테스트 대상).

## 테스트

```bash
# 전체
make test-py      # pytest (4개 Python 서비스)
make test-rust    # cargo test (risk-engine + tui)
make test-web     # vitest (bff + dashboard)

# 개별
cd services/ingest && uv run pytest tests/ -v
export PATH=$HOME/.cargo/bin:$PATH && cargo test -p risk-engine
cd web && pnpm -r test
```


## 트러블슈팅

| 이슈                                           | 원인                                           | 조치                                                             |
| ---------------------------------------------- | ---------------------------------------------- | ---------------------------------------------------------------- |
| `make up` YAML 파싱 오류                       | `env_file: [.env.${ENV:-dev}]` 의 `:-`         | 값 인용 `[".env.${ENV:-dev}"]` (수정 완료)                       |
| `cargo: command not found`                     | PATH 미설정                                    | `export PATH=$HOME/.cargo/bin:$PATH`                             |
| `Cannot connect to Docker daemon`              | Docker Desktop 미실행                          | `open -a Docker` 후 ~30초 대기                                   |
| `finance-datareader not found`                 | PyPI 패키지명                                  | `finance-datareader` (하이픈)                                    |
| `Cannot switch to pnpm@9`                      | 무효 버전 핀                                   | `pnpm@9.15.0` (수정 완료)                                        |
| pytest mock 오염                               | 공유 DataFrame in-place 변형                   | `df.rename(columns=str.lower)` 비파괴                            |
| bff `Cannot find name 'process'`(TS2580)       | bff 에 `@types/node` 누락                      | devDeps `@types/node` + tsconfig `types:["node"]` (수정 완료)    |
| `pnpm install --offline` 가 node_modules purge | 부유 버전(`19.x`) 재해석 → 전이의존성 미스토어 | 온라인 `pnpm install` 또는 `--frozen-lockfile`. `--offline` 지양 |
| `make mpm-stop` 후 :3000 잔존                  | `next dev` 워커가 프로세스그룹 escape          | stop=honcho graceful + 그룹 SIGTERM sweep (수정 완료)            |

## 프로덕션 배포 가이드

> ⚠️ **보안 원칙**: 실 시크릿(DB 비밀번호, API 키, JWT 시크릿 등)은 파일에 절대 기재하지 않습니다.
> HashiCorp Vault 또는 K8s External Secrets Operator를 통해 런타임 주입합니다.

### prod 전체 기동 — `make prod-all`

> `AUTH_JWT_SECRET` 쉘 export 필수 (컨테이너 주입):
> ```bash
> export AUTH_JWT_SECRET=$(openssl rand -base64 32)
> ```

| 명령 | 동작 |
|------|------|
| `make prod-all` | 인프라(postgres·redis) + 전체 앱 컨테이너 기동 (`ENV=prod`) |
| `make prod-stop` | 전 컨테이너 중지 및 제거 |
| `make prod-logs` | 통합 로그 tail |
| `make prod-status` | 컨테이너 상태 확인 |
| `make prod-build` | Docker 이미지 빌드 (`ENV=prod`) |
| `make deploy` | K8s Helm 배포 |

```bash
# 최초 또는 이미지 변경 시
make prod-build

# 기동
make prod-all

# 로그 확인
make prod-logs

# 종료
make prod-stop
```

### 환경 설정 — `.env.prod`

```bash
# .env.prod — 값 플레이스홀더만 기재, 실값은 Vault/External Secrets가 주입
APP_ENV=prod
DATABASE_URL=${DATABASE_URL}         # Vault → K8s Secret → 파드 env
REDIS_URL=${REDIS_URL}
ENV=prod
RISK_ENGINE_PORT=3001
NEXT_PUBLIC_API_BASE=${NEXT_PUBLIC_API_BASE}
ANALYSIS_URL=${ANALYSIS_URL}
RAG_URL=${RAG_URL}
INGEST_URL=${INGEST_URL}
# 모든 시크릿: K8s Secret → External Secrets Operator → Vault
```

### K8s + Helm 배포 흐름 (선택)

```bash
make deploy   # helm upgrade --install stock-trader ./deploy/helm
```

> 현재 `deploy/helm` 차트가 미생성 상태입니다. 배포 전 Helm 차트를 먼저 작성해야 합니다.

### B) K8s + Helm 배포 흐름

```
[소스코드] → docker build → [컨테이너 레지스트리]
                                    ↓
[Helm chart] → helm upgrade → [K8s Deployment/Service]
                                    ↓
[External Secrets Operator] ← [HashiCorp Vault]
          ↓ 동기화
[K8s Secret] → 파드 env 주입
```

```bash
# 전제: kubectl, helm, K8s 클러스터 구성 완료
# 1. Helm 차트 배포
make deploy

# 2. 또는 직접 실행
helm upgrade --install stock-trader ./deploy/helm \
  --namespace stock-trader \
  --create-namespace \
  --values deploy/helm/values-prod.yaml
```

### C) HashiCorp Vault + K8s External Secrets 주입 방법

#### 1단계 — Vault에 시크릿 저장

```bash
# Vault 로그인 (OIDC/AppRole 등 조직 정책에 따라)
vault login

# KV v2 엔진에 시크릿 저장
vault kv put secret/stock-trader/prod \
  DATABASE_URL="postgresql://user:pass@host:5432/stock_trader" \
  REDIS_URL="redis://:pass@host:6379/0" \
  JWT_SECRET="..." \
  OPENAI_API_KEY="..."
```

#### 2단계 — External Secrets Operator 설치

```bash
helm repo add external-secrets https://charts.external-secrets.io
helm install external-secrets external-secrets/external-secrets \
  -n external-secrets-system --create-namespace
```

#### 3단계 — SecretStore (Vault 연결) 생성

```yaml
# deploy/k8s/secret-store.yaml
apiVersion: external-secrets.io/v1beta1
kind: SecretStore
metadata:
  name: vault-backend
  namespace: stock-trader
spec:
  provider:
    vault:
      server: "https://vault.example.com"
      path: "secret"
      version: "v2"
      auth:
        kubernetes:
          mountPath: "kubernetes"
          role: "stock-trader-prod"
```

#### 4단계 — ExternalSecret (자동 K8s Secret 생성)

```yaml
# deploy/k8s/external-secret.yaml
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: stock-trader-secrets
  namespace: stock-trader
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: vault-backend
    kind: SecretStore
  target:
    name: stock-trader-prod-secrets   # ← 생성될 K8s Secret 이름
    creationPolicy: Owner
  data:
    - secretKey: DATABASE_URL
      remoteRef: { key: stock-trader/prod, property: DATABASE_URL }
    - secretKey: REDIS_URL
      remoteRef: { key: stock-trader/prod, property: REDIS_URL }
    - secretKey: JWT_SECRET
      remoteRef: { key: stock-trader/prod, property: JWT_SECRET }
```

#### 5단계 — Helm values에서 Secret 참조

```yaml
# deploy/helm/values-prod.yaml
envFrom:
  - secretRef:
      name: stock-trader-prod-secrets   # ExternalSecret이 생성한 K8s Secret
```

파드는 `DATABASE_URL`, `REDIS_URL` 등을 환경변수로 자동 수신합니다. 파일(`.env.prod`)에는 실값이 없으므로 Git 커밋 안전.

### 시크릿 로테이션

Vault에서 시크릿을 갱신하면 External Secrets Operator가 `refreshInterval`(기본 1h)마다 K8s Secret을 자동 동기화합니다. 파드 재시작 없이 반영하려면 Reloader(Stakater) 연동을 권장합니다.
