**English** | [한국어](README.md)

# Stock Trader AI Platform

> Real-time stock trading AI platform — Finance domain (KSIC K).
> Compliance: 전자금융감독규정 · ISMS-P · PCI-DSS 4.0.1 → [COMPLIANCE.md](COMPLIANCE.md)

## Overview

profile: `python-fastapi` (+ `rust-axum` core, `node-next-nest` web) · domain: `finance`

| Doc | Link |
|-----|------|
| Compliance guide | [COMPLIANCE.md](COMPLIANCE.md) |
| Env template | [.env.example](.env.example) |

![Stock Trader AI Platform Demo](Stock-Trader.gif)

## Implementation Status (PRD mapping)

| Feature | Service | Status | Notes |
|---------|---------|--------|-------|
| F1.1 Price/OHLCV/tickers | ingest | ✅ | FinanceDataReader |
| F1.2 Order book | ingest | ✅ | Price-based simulation |
| F1.2 Broker WS feed | ingest | ✅ | Real WS / random-walk sim fallback |
| F1.2 Adaptive flow control | ingest | ✅ | **AIMD rate + priority queue + backpressure** — integrated into `SubscriptionManager` token bucket (opt-in) |
| F1.5 KRX OPEN API collector | ingest | ✅ | 2-step OTP→data, OHLCV + investor flow, fallback when key not set |
| F1.3 News RSS | ingest | ✅ | feedparser |
| F1.4 FastMCP | ingest | ✅ | Claude/Gemini integration |
| F2.1 Indicators | analysis | ✅ | RSI·MACD·Bollinger·EMA·SMA·ATR |
| F2.2 Prediction | analysis | ✅ | Multivariate (macro 17 modes + **erc_quest_adaptive (adaptive-grid QuEST)·erc_factor (MP factor/noise split)** + MP goodness-of-fit + FinBERT/KR-FinBERT) |
| F2.3 Screener | analysis | ✅ | RSI·volume filters |
| F3.1 Multi-agent | agents | ✅ | Scraper·Analyst·Portfolio·Decision |
| F3.3 Self-correction loop | agents | ✅ | **Strategy-drift monitor (churn·low-confidence·weight-breach) + HOLD downgrade·weight clamp** |
| F3.2 Quant RAG | rag | ✅ | Hybrid search + hallucination block + pgvector persistence |
| F4 Risk engine | risk-engine | ✅ | Stop-Loss·Trailing·daily limit·Fail-Safe |
| F5 Backtesting | analysis | ✅ | Multi-strategy + RL (…·DPG **reinforce/a2c/ppo·GAE**) + **persistent worker pool·shared memory** |
| F5 Paper trading | risk-engine | ✅ | Multi-ticker·rolling·5-factor·full VAR(p)·YW + companion complex eigenvalue QR(Schur) radius projection + **multi-account (isolated per-account ledger)** |
| F6.1 Scalper TUI | apps/tui | ✅ | ratatui order book·P&L |
| F6.2 Web dashboard | web | ✅ | Next.js + NestJS BFF + **4-quadrant candle chart (5m intraday · hourly · weekday · daily)** + **dark/light theme toggle · tooltips** + **TopBar ticker+name with localStorage persistence** + sub-page auto-query (risk/backtest/agents) |
| F7 Simulation buy/sell | web/risk | ✅ | Dashboard buy▲/sell▼ panel (SimulationPanel) → BFF POST /api/paper/execute → risk-engine paper ledger · **virtual cash tracking (user-set initial deposit, deduct on buy / add on sell)** → portfolio enriched with current price · name · P&L · weight via BFF |
| F8 User Auth | web | ✅ | Register/Login (bcryptjs + jose JWT + TOTP otplib), **user-specified deposit at registration**, **Sidebar roll-up MyPage** (password · deposit · TOTP), AuthGuard route protection, SQLite (`node:sqlite` Node 24 built-in, `globalThis` HMR singleton) |
| F6.3 Alerts | agents | ✅ | Telegram/Discord webhook |
| F6.3 Two-way control | agents + risk-engine | ✅ | **remote bot stop(halt)/emergency liquidation + inbound commands (secret auth)** |
| F9 Service health | web/bff | ✅ | Sidebar real-time health polling (30s) · BFF `/api/services/health` parallel check |
| F10 Docker prod | web | ✅ | BFF·Dashboard multi-stage Dockerfile · Next.js standalone · **`make prod-all`** / `make prod-stop` |

## Architecture / Service Roles

```
Stock-Trader/
├── services/
│   ├── ingest/     F1 Price·orderbook·news·FastMCP·AIMD flow  :8003  Python/FastAPI
│   ├── analysis/   F2 Indicators·prediction·screener·RL(persistent) :8001  Python/FastAPI
│   ├── rag/        F3.2 Quant RAG                            :8002  Python/FastAPI
│   └── agents/     F3.1 Multi-agent·F3.3 self-correct·F6.3 control :8004  Python/FastAPI
├── core/risk-engine/  F4 Stop-Loss/Trailing·F6.3 halt/liquidate :3001  Rust/Axum
├── Procfile.dev       MPM static orchestration (make dev-all)
├── tools/mpm/         MPM Procfile generator (registry·ENV·groups, make mpm)
├── apps/tui/          F6.1 Scalper console                   Rust/ratatui
└── web/
    ├── apps/dashboard  F6.2 Dashboard                 :3000  Next.js 15
    └── apps/bff        BFF aggregation gateway        :3002  NestJS 11
```

Infrastructure: PostgreSQL 17 (pgvector 0.8.2) + Redis 7.4

## Prerequisites

| Tool | Version (verified) | Check |
|------|--------------------|-------|
| Python | 3.12+ (venv 3.13.12) | `python3 --version` |
| uv | 0.4+ | `uv --version` |
| Node.js | 20 LTS+ (v26) | `node --version` |
| pnpm | 9+ (10.33) | `pnpm --version` |
| Rust/cargo | 1.80+ (1.95) | `cargo --version` |
| Docker Desktop | latest | `docker info` |

> **cargo PATH**: add `export PATH=$HOME/.cargo/bin:$PATH` to `~/.zshrc`

## Environment Setup

```bash
cp .env.example .env.local   # root + each service dir
```

| File | Purpose |
|------|---------|
| `.env.local` | Local direct run (SQLite, optional Redis) |
| `.env.prod` | Key list only — injected by Vault/K8s External Secrets |

> **⚠️ Real broker API Key/Secret → OS Keychain or Vault only. Never write to files.**
> Non-production environments must use synthetic data only (COMPLIANCE.md).

### AUTH_JWT_SECRET Configuration

The dashboard (F8 user auth) requires `AUTH_JWT_SECRET` (random value, 32+ bytes) to sign JWTs.

**Generate:**
```bash
openssl rand -base64 32
```

| Env | Method | Notes |
|-----|--------|-------|
| `local` | Write directly in `.env.local` | Temporary dev value allowed |
| `prod` | `export` in shell before make (K8s: injected by Vault automatically) | Never write to file |

> **Docker Compose env_file caveat:** `${AUTH_JWT_SECRET}` in `.env.prod` is **not shell-expanded** by Docker Compose. You must `export` the value in your shell before running make.

```bash
# prod — set in shell before Docker Compose
export AUTH_JWT_SECRET=$(openssl rand -base64 32)
make prod-all

# macOS Keychain (long-term storage)
security add-generic-password -a stock-trader -s AUTH_JWT_SECRET \
  -w "$(openssl rand -base64 32)"
export AUTH_JWT_SECRET=$(security find-generic-password \
  -a stock-trader -s AUTH_JWT_SECRET -w)
make prod-all
```

Each service loads its own `.env.local` from CWD via pydantic-settings:
```
services/ingest/.env.local, services/analysis/.env.local, ...
```

## Running

### A) docker compose (multi-service)

```bash
# ── Environment setup (first install · stale node_modules / .venv) ──
make setup               # ENV=local (default) — delete web/node_modules + services/*/.venv, reinstall + uv sync
make setup-local         # local shortcut (stops services → reinstall → ready for make local-all)
make setup-prod          # prod shortcut  — image build only

make up                  # infra only (postgres+pgvector, redis). ENV=local
make up-app              # full app stack (app profile) as containers
make build               # docker compose --profile app build
make sync                # sync all deps (uv sync + pnpm install)
make dev-ingest          # individual service (uvicorn --reload, volume mount)
make dev-analysis / dev-rag / dev-agents / dev-risk / dev-tui / dev-web
make local-all           # start all services in background (recommended; stops existing first)
make local-stop          # stop all services
make local-logs          # tail aggregated log
make local-status        # process status
make dev-all             # foreground start (blocks terminal, Ctrl-C to stop all)
make down                # stop all
```

### MPM (multi-process manager) — `make local-all` (recommended)

Starts and manages all 6 processes (ingest·analysis·rag·agents·risk·web) from **a single terminal**. Runs honcho through `uvx`, so **no separate install** is needed.

> ⚠️ Running `make local-all` (background) and `make dev-all` (foreground) **at the same time causes port conflicts** and forces services to terminate. Use only one at a time.

```bash
# ── Recommended: background ─────────────────────────────────
make local-all                    # ENV=local start all services in background (stops existing first)
make local-stop                   # stop all services
make local-logs                   # tail aggregated log (.mpm/mpm.log)
make local-status                 # process status (pid)

# ── Foreground (blocks terminal, colorised log) ──────────────
make dev-all                      # Ctrl-C to stop all

# ── Low-level MPM commands ───────────────────────────────────
make mpm ENV=local GROUP="py rust"  # python+rust groups only
make mpm-check ENV=local GROUP=py   # validate generated Procfile (exit code)
```

### B) Production — Docker Compose (`make prod-all`)

> `AUTH_JWT_SECRET` must be exported before running (see above).

| Command | Action |
|---------|--------|
| `make prod-build` | Build Docker images (`ENV=prod`) |
| `make prod-all` | Start infra (postgres·redis) + all app containers |
| `make prod-stop` | Stop and remove all containers |
| `make prod-logs` | Tail aggregated container logs |
| `make prod-status` | Show container status |

```bash
# First run or after image changes
make prod-build

# Start
make prod-all

# Logs
make prod-logs

# Stop
make prod-stop
```

> **tools/mpm**: deterministically renders the honcho Procfile per ENV·group from a single service registry (`SERVICES`), and starts/stops/inspects all processes in the **background (detached)**. `make mpm` = `mpm.py up` (Popen `start_new_session` + `.mpm/{Procfile.gen,mpm.pid,mpm.log}`); `make mpm-stop` = honcho SIGTERM (graceful cascade) + session process-group sweep (cleans even detached `next dev` workers). Groups `py` (ingest·analysis·rag·agents)·`rust` (risk)·`web`. ENV substitution (`APP_ENV`·`.env.{env}`). Standard library only (zero deps). State in `.mpm/` (gitignored).

> **ENV passthrough**: all compose targets (`up`/`up-app`/`build`/`down`) pass `ENV=$(ENV)` to docker compose, selecting `.env.$(ENV)`. Rust targets (`dev-risk`/`dev-tui`) load `.env.$(ENV)` as env vars before running.

compose profiles:
- `default`: postgres, redis (`make up`)
- `app`: all service containers (`make up-app`)

### B) Direct host execution

```bash
# Python services (per dir)
cd services/ingest && uv sync --dev && uv run uvicorn app.main:app --reload --port 8003
cd services/analysis && uv run uvicorn app.main:app --reload --port 8001
cd services/rag && uv run uvicorn app.main:app --reload --port 8002
cd services/agents && uv run uvicorn app.main:app --reload --port 8004

# Rust
export PATH=$HOME/.cargo/bin:$PATH
cargo run -p risk-engine        # :3001
cargo run -p tui                # scalper console (terminal)

# FastMCP server (F1.4)
cd services/ingest && uv run mcp run app/services/mcp_server.py

# Web (pnpm workspace)
cd web && pnpm install
pnpm --filter @stock-trader/bff dev         # :3002
pnpm --filter @stock-trader/dashboard dev   # :3000
```

## Port / URL Reference

| Service | URL | Port | Profile | API Docs |
|---------|-----|------|---------|---------|
| ingest | http://localhost:8003 | 8003 | app | [/docs](http://localhost:8003/docs) |
| analysis | http://localhost:8001 | 8001 | app | [/docs](http://localhost:8001/docs) |
| rag | http://localhost:8002 | 8002 | app | [/docs](http://localhost:8002/docs) |
| agents | http://localhost:8004 | 8004 | app | [/docs](http://localhost:8004/docs) |
| risk-engine | http://localhost:3001 | 3001 | app | — |
| bff | http://localhost:3002 | 3002 | — | /api/health |
| dashboard | http://localhost:3000 | 3000 | — | — |
| postgres | localhost:5432 | 5432 | default | — |
| redis | localhost:6379 | 6379 | default | — |

## Dashboard Persona

The `?persona=` query param (dashboard URL and `agents/analyze` API) selects trading style. Persona directly affects risk parameters, position-weight limits, and agent decision thresholds.

| Persona | URL value | Hold period | Notes |
|---------|-----------|-------------|-------|
| Scalper | `scalper` | Seconds – minutes | Ultra-short. Tight stop-loss, rapid entry/exit, high turnover. Minimum weight limit (default 5%). |
| Day Trader | `day` | Intraday (closed EOD) | No overnight. Medium stop-loss, daily P&L limit takes priority. Medium weight limit (default 8%). |
| Swing | `swing` | Days – weeks | Trend-following. Standard stop-loss + trailing stop. Standard weight limit (default 10%). **Default.** |
| Position | `position` | Weeks – months | Long-term hold. Wide stop-loss, macro/fundamental inputs weighted up. Max weight limit (default 15%). |

> Dashboard URL example: `http://localhost:3000/?ticker=005930&persona=scalper`
> Agent API: pass `"persona": "day"` in the `POST /agents/analyze` body.
> Self-correction (`/agents/self_correct`) applies the per-persona weight limit when judging drift.

## API Examples

### F1 ingest
```bash
curl http://localhost:8003/market/price/005930
curl "http://localhost:8003/market/ohlcv/005930?days=30"
curl http://localhost:8003/market/tickers/KRX
curl "http://localhost:8003/orderbook/005930?levels=10"
curl http://localhost:8003/news/sources
curl http://localhost:8003/news/reuters-business?limit=10
```

### F2 analysis + F5 backtesting
```bash
curl "http://localhost:8001/indicators/005930?days=60"
curl http://localhost:8001/predict/005930                       # linear (fast)
curl "http://localhost:8001/predict/005930?model=lstm"          # LSTM
curl "http://localhost:8001/predict/005930?model=transformer"   # Transformer
curl -X POST "http://localhost:8001/predict/005930/train?arch=transformer"  # pretrain → checkpoint
curl -X POST http://localhost:8001/predict/retrain -H 'content-type: application/json' \
  -d '{"tickers":["005930","000660"],"arch":"lstm","max_age_hours":24}'      # scheduled retrain (stale only)

curl -X POST http://localhost:8001/screener/ -H 'content-type: application/json' \
  -d '{"market":"KRX","rsi_max":30,"limit":10}'

# F5 multi-strategy backtesting (sma_cross | rsi_threshold | macd_cross | qlearn)
curl http://localhost:8001/backtest/strategies
curl -X POST http://localhost:8001/backtest/ -H 'content-type: application/json' \
  -d '{"ticker":"005930","days":365,"strategy":"rsi_threshold","params":{"rsi_buy_below":30,"rsi_sell_above":70}}'

# F5 reinforcement learning — Q-learning (tabular) / DQN (neural net)
curl -X POST http://localhost:8001/backtest/rl  -H 'content-type: application/json' \
  -d '{"ticker":"005930","days":365,"episodes":50}'
curl -X POST http://localhost:8001/backtest/dqn -H 'content-type: application/json' \
  -d '{"ticker":"005930","days":365,"episodes":30}'   # Rainbow-grade DQN (Double·Dueling·PER·n-step·Noisy)
curl -X POST http://localhost:8001/backtest/c51 -H 'content-type: application/json' \
  -d '{"ticker":"005930","days":365,"episodes":20}'   # Distributional C51
curl -X POST "http://localhost:8001/backtest/qrdqn?mode=fqf&cvar_alpha=0.25&fqf_state_dependent=true" \
  -H 'content-type: application/json' -d '{"ticker":"005930","days":365,"episodes":15}'  # QR/IQN/FQF + CVaR
curl -X POST "http://localhost:8001/backtest/dpg?mode=ppo&n_rollouts=4&parallel=true&executor=process" -H 'content-type: application/json' \
  -d '{"ticker":"005930","days":365,"episodes":20}'   # DPG (PPO·minibatch·KL) + multiprocess (state_dict replication) parallel rollouts
curl -X POST "http://localhost:8001/backtest/dpg?mode=a2c&n_rollouts=4&parallel=true&executor=persistent" -H 'content-type: application/json' \
  -d '{"ticker":"005930","days":365,"episodes":20}'   # persistent worker pool (reused) + shared-memory (SharedMemory) tensors
# {"executor":"persistent",...} — px/rsi loaded once, pool reused. Identical result to process·sequential (deterministic)
# Persistent pool (MPM): worker count via BACKTEST_PERSIST_WORKERS env, BrokenProcessPool auto-recreate, persistent_pool_stats()
```

> RL parallel-rollout `executor`: `thread` (shared model) · `process` (pool created per episode, state_dict replication) · `persistent` (reused pool + `SharedMemory` zero-copy px/rsi mapping — removes pool-recreation cost). All three give identical results to sequential via per-rollout seeds.

> Macro channel: `MACRO_INDICES` multi-indicator + `MACRO_COMBINE` 17 modes (…·erc_lw·erc_cc·erc_oas·erc_nlw·erc_quest·erc_quest_grid·**erc_quest_adaptive** (quantile-node adaptive-grid QuEST)·**erc_factor** (keep eigenvalues above MP edge λ⁺ as signal·flatten bulk = RMT denoising)·pca·ipca·ccipca). Diagnostic: `marchenko_pastur_gof(eigs, c)` = KS distance of sample eigenvalues vs MP law (signal detection). News sentiment uses FinBERT (`FINBERT_MODEL`=`ProsusAI/finbert` or KR `snunlp/KR-FinBert-SC`) when `FINBERT_ENABLED=true`, else keyword. Neutral fallback on source/model failure.

### F3 rag / agents
```bash
curl -X POST http://localhost:8002/rag/ingest -H 'content-type: application/json' \
  -d '{"documents":[{"id":"fed1","content":"Fed held rates at 5.5%","meta":{}}]}'
curl -X POST http://localhost:8002/rag/query -H 'content-type: application/json' \
  -d '{"query":"fed interest rates","k":3}'
# grounded:false when no evidence (hallucination block)

curl -X POST http://localhost:8004/agents/analyze -H 'content-type: application/json' \
  -d '{"ticker":"005930","persona":"swing"}'

# F3.3 self-correction — drift verdict + conservative correction from history+candidate
curl -X POST http://localhost:8004/agents/self_correct -H 'content-type: application/json' \
  -d '{"persona":"scalper","history":[{"signal":"BUY","confidence":0.8,"weight":0.1}],
       "candidate":{"signal":"BUY","confidence":0.8,"weight":0.5}}'
# {"drift":{"drift":true,"reasons":["weight_breach(...)"],...},
#  "corrected":{"signal":"BUY","weight":0.1,"corrected":true,"corrections":["weight_clamped_to_0.1"]}}
# churn (frequent BUY↔SELL)·low-confidence → corrected.signal="HOLD" (downgrade)

# F6.3 alerts (unconfigured channels → false / no-op)
curl -X POST http://localhost:8004/notify/ -H 'content-type: application/json' \
  -d '{"event":"STOP_LOSS","payload":{"ticker":"005930","price":68600}}'

# F6.3 two-way control — inbound commands (secret auth required; 403 rejects all if CONTROL_SECRET unset)
curl -X POST http://localhost:8004/control/command -H 'content-type: application/json' \
  -d '{"secret":"<control-secret>","text":"/stop"}'        # emergency bot halt
# {"command":"/stop","result":{"halted":true}}
curl -X POST http://localhost:8004/control/command -H 'content-type: application/json' \
  -d '{"secret":"<control-secret>","text":"/liquidate","prices":{"005930":71000}}'  # emergency liquidate
# {"command":"/liquidate","result":{"liquidated":1,"realized_pnl":..,"halted":true}}
# /resume · /status. Telegram webhook: POST /control/telegram?secret=... (or X-Telegram-Bot-Api-Secret-Token header)
```

### F4 risk-engine + paper trading
```bash
curl -X POST http://localhost:3001/risk/check -H 'content-type: application/json' \
  -d '{"ticker":"005930","entry_price":70000,"current_price":68600,
       "stop_loss_pct":0.02,"daily_loss_limit_pct":0.05,"max_position_pct":0.10}'
# {"action":"force_sell","triggered":["stop_loss"],...}

# Simulated (paper) fill — NOT real trading. Multi-ticker·slippage·fees·append-only ledger
# DATABASE_URL=postgres → paper_fills persistence + restart hydration
# client_order_id = idempotency key (optional). Same key on retry fills once only (ledger+DB dedup, COMPLIANCE §4.1)
curl -X POST http://localhost:3001/paper/execute -H 'content-type: application/json' \
  -d '{"ticker":"005930","side":"buy","quantity":10,"price":70000,"client_order_id":"ord-20260607-001"}'
# Retry (same client_order_id) → {"accepted":true,"reason":"중복 주문(멱등키) — 기존 체결 반환",...} (no re-fill)
curl http://localhost:3001/paper/portfolio
# {"positions":[...],"realized_pnl":..,"realized_by_ticker":{...},"fills":N}

# Multi-account — ?account= for isolated ledgers (unset=default). DB persistence: default only; named accounts in-memory.
curl -X POST "http://localhost:3001/paper/execute?account=strat-A" -H 'content-type: application/json' \
  -d '{"ticker":"005930","side":"buy","quantity":10,"price":70000}'
curl "http://localhost:3001/paper/portfolio?account=strat-A"   # {"account":"strat-A","positions":[...],...}
curl http://localhost:3001/paper/accounts                       # {"accounts":["default","strat-A"]}

# mark-to-market — current prices → per-ticker unrealized + equity-curve point
curl -X POST http://localhost:3001/paper/mark -H 'content-type: application/json' \
  -d '{"005930":75000,"000660":115000}'
curl http://localhost:3001/paper/equity_curve              # raw curve (DB-persisted if DATABASE_URL)
curl "http://localhost:3001/paper/equity_agg?period=daily" # daily|weekly|monthly|quarterly OHLC
curl -X POST http://localhost:3001/paper/alpha -H 'content-type: application/json' \
  -d '{"initial_capital":10000000,"benchmark":[2400,2450,2500]}'  # benchmark alpha
curl -X POST http://localhost:3001/paper/risk_metrics -H 'content-type: application/json' \
  -d '{"initial_capital":10000000,"benchmark":[2400,2440,2420,2480]}'  # beta·info-ratio·tracking-error
curl -X POST http://localhost:3001/paper/risk_rolling -H 'content-type: application/json' \
  -d '{"initial_capital":10000000,"benchmark":[...],"window":20}'      # rolling-window metrics
curl -X POST http://localhost:3001/paper/factor_regression -H 'content-type: application/json' \
  -d '{"initial_capital":10000000,"factors":[[..mkt..],[..smb..],[..hml..]]}'  # Fama-French OLS
curl -X POST http://localhost:3001/paper/factor_regression_nw -H 'content-type: application/json' \
  -d '{"initial_capital":10000000,"factors":[[mkt],[smb],[hml],[rmw],[cma]],"lag":4}'  # 5-factor + Newey-West HAC SE
curl -X POST http://localhost:3001/paper/factor_regression_nw_auto -H 'content-type: application/json' \
  -d '{"initial_capital":10000000,"factors":[[mkt],[smb],[hml]]}'  # Andrews auto-bandwidth → lag_auto
curl -X POST http://localhost:3001/paper/factor_regression_qs -H 'content-type: application/json' \
  -d '{"initial_capital":10000000,"factors":[[mkt],[smb],[hml]],"prewhiten":true,"full_var":true}'  # QS + full VAR(1)
curl -X POST http://localhost:3001/paper/factor_regression_qs_aic -H 'content-type: application/json' \
  -d '{"initial_capital":10000000,"factors":[[mkt],[smb],[hml]],"max_order":5}'  # AIC diagonal AR(p)
curl -X POST http://localhost:3001/paper/factor_regression_qs_var -H 'content-type: application/json' \
  -d '{"initial_capital":10000000,"factors":[[mkt],[smb],[hml]],"max_order":3,"criterion":"bic","stabilize":true,"companion":true}'  # full VAR(p)·BIC/HQ + companion projection

# F6.3 emergency control (risk-engine direct) — endpoints the agents /control delegates to
curl -X POST http://localhost:3001/control/halt -H 'content-type: application/json' -d '{"halted":true}'
curl http://localhost:3001/control/status        # {"halted":true,"open_positions":N}
# Per-account control: ?account=strat-A (halt·status·liquidate are account-independent)
# halt=true blocks new /paper/execute orders. Liquidation is halt-independent (Fail-Safe).
curl -X POST http://localhost:3001/control/liquidate -H 'content-type: application/json' \
  -d '{"prices":{"005930":71000,"000660":121000}}'  # market-sell all positions + auto-halt
# {"liquidated":2,"fills":[...],"realized_pnl":..,"halted":true}  (liquidation fills kept in append-only ledger)
```

### F1.5 KRX OPEN API
```bash
curl http://localhost:8003/krx/status
# {"configured":false,"note":"Set KRX_OPEN_API_KEY env var to activate."}

curl "http://localhost:8003/krx/ohlcv/005930?from_date=20260101&to_date=20260131&market=KOSPI"
# key not set: {"ticker":"005930","configured":false,"bars":[],"count":0}
# key set: {"bars":[{"date":"2026-01-01","open":70000,"high":71000,...,"source":"krx_openapi"}],...}

curl "http://localhost:8003/krx/investor-flow/005930"
# key not set: {"ticker":"005930","configured":false,"phase":"A_pending","flows":[],"count":0}
# key set: {"flows":[{"date":"..","institution":125000,"foreign":-48000,"individual":-77000}],...}
```
> 2-step KRX OPEN API call: OTP (`GenerateOTP.jspx`) → data (`jsonSvr.do`). Empty result when key not set; FinanceDataReader fallback stays active. API IDs: KOSPI=`stk_bydd_trd` / KOSDAQ=`ksq_bydd_trd` / investor=`stk_invsr_trd_by_isu`. Min 0.5s between calls (`KRX_API_RATE_LIMIT`).

### F1.2 broker tick feed (WebSocket)
```
ws://localhost:8003/market/feed/005930
# If BROKER_WS_URL set: BROKER_PROTOCOL=generic|kis, auth (BROKER_API_KEY/SECRET) +
# heartbeat ping-pong (BROKER_HEARTBEAT_INTERVAL/TIMEOUT) + backoff reconnect (BROKER_MAX_RETRIES, -1=inf).
# Else simulated.
ws://localhost:8003/market/feed_multi/005930,000660   # multi-ticker multiplexing (single WS)
```
> **Adaptive flow control (integrated)**: `SubscriptionManager` opt-in — with `aimd=AIMDRateController(...)` the global token-bucket rate auto-adjusts via AIMD (ack success = additive increase / subscription failure = multiplicative decrease). With `command_capacity`/`command_watermark`, pending commands are managed by a priority queue (unsubscribe prioritized, lowest-priority dropped on overflow, `command_backpressured()` signal). Unset → legacy FIFO·fixed rate (backward compatible). Pure flow-control units: [adaptive_flow.py](services/ingest/app/services/adaptive_flow.py).

### F6.2 BFF aggregation + real-time candles
```bash
curl "http://localhost:3002/api/dashboard/005930?persona=swing"

curl "http://localhost:3002/api/candles/005930?days=30"   # candles (OHLCV) — ingest proxy (days clamped 1~365)
# {"ticker":"005930","bars":[{"date":..,"open":..,"high":..,"low":..,"close":..,"volume":..}],"count":30}
```
> The dashboard candle chart (`components/CandleChart.tsx`) loads initial bars from `/api/candles` and polls `/api/price` every 5s to update the forming candle's close/high/low in real time (direct SVG render, no charting library). Geometry is isolated in pure functions in [lib/candles.ts](web/apps/dashboard/lib/candles.ts) (tested).

## Testing

```bash
make test-py      # pytest (4 Python services)
make test-rust    # cargo test (risk-engine + tui)
make test-web     # vitest (bff + dashboard)

# individual
cd services/ingest && uv run pytest tests/ -v
export PATH=$HOME/.cargo/bin:$PATH && cargo test -p risk-engine
cd web && pnpm -r test
```


## Troubleshooting

| Issue | Cause | Fix |
|-------|-------|-----|
| `make up` YAML parse error | `:-` in `env_file: [.env.${ENV:-dev}]` | quote value `[".env.${ENV:-dev}"]` (fixed) |
| `cargo: command not found` | PATH not set | `export PATH=$HOME/.cargo/bin:$PATH` |
| `Cannot connect to Docker daemon` | Docker Desktop not running | `open -a Docker`, wait ~30s |
| `finance-datareader not found` | PyPI package name | `finance-datareader` (hyphen) |
| `Cannot switch to pnpm@9` | invalid version pin | `pnpm@9.15.0` (fixed) |
| pytest mock contamination | shared DataFrame in-place mutation | `df.rename(columns=str.lower)` (non-destructive) |
| bff `Cannot find name 'process'` (TS2580) | `@types/node` missing in bff | devDeps `@types/node` + tsconfig `types:["node"]` (fixed) |
| `pnpm install --offline` purges node_modules | floating ranges (`19.x`) re-resolve → transitive dep not in store | online `pnpm install` or `--frozen-lockfile`. avoid `--offline` |
| port :3000 lingers after `make mpm-stop` | `next dev` workers escape the process group | stop = honcho graceful + group SIGTERM sweep (fixed) |
