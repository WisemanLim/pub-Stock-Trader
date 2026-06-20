// stock-trader risk-engine — 초저지연 리스크/체결 코어 (F4, 목표: 10ms)
// Stop-Loss · Trailing Stop · Take-Profit · 일일 최대손실 한도 · 포지션 사이징 · Fail-Safe
// + F5 가상(시뮬레이션) 체결 추적 (다종목 + postgres 영속화) — 실거래 아님.
mod paper;
mod paper_db;
mod risk;

use axum::extract::State;
use axum::{http::StatusCode, routing::get, routing::post, Json, Router};
use paper::{list_accounts, with_account_book, with_book, OrderRequest, Prepared, DEFAULT_ACCOUNT};
use risk::{evaluate, RiskRequest};
use serde_json::json;
use sqlx::PgPool;
use std::sync::Arc;

#[derive(Clone)]
struct AppState {
    pool: Option<Arc<PgPool>>,
}

#[tokio::main]
async fn main() {
    tracing_subscriber::fmt::init();

    // DB 영속화 — DATABASE_URL 이 postgres 면 풀 생성 + 원장 하이드레이션.
    let dsn = std::env::var("DATABASE_URL").unwrap_or_default();
    let pool = if dsn.starts_with("postgres") {
        match paper_db::init(&dsn).await {
            Some(p) => {
                if let Ok(fills) = paper_db::load_fills(&p).await {
                    with_book(|b| b.replay(&fills));
                    tracing::info!("paper ledger hydrated: {} fills", fills.len());
                }
                if let Ok(points) = paper_db::load_equity(&p).await {
                    let n = points.len();
                    with_book(|b| b.equity_curve = points);
                    tracing::info!("equity curve hydrated: {} points", n);
                }
                Some(Arc::new(p))
            }
            None => {
                tracing::warn!("DATABASE_URL set but connect failed → in-memory paper book");
                None
            }
        }
    } else {
        // postgres 없음 → JSON 스냅샷 파일로 이전 상태 복원.
        if let Some(snap) = paper_db::load_snapshot() {
            with_book(|b| b.restore_from_snapshot(snap));
            tracing::info!("paper book restored from snapshot");
        }
        None
    };

    let no_db = pool.is_none();
    let state = AppState { pool };
    let app = Router::new()
        .route("/health", get(health))
        .route("/risk/check", post(risk_check))
        .route("/paper/execute", post(paper_execute))
        .route("/paper/set-cash", post(paper_set_cash))
        .route("/paper/accounts", get(paper_accounts))
        .route("/control/halt", post(control_halt))
        .route("/control/status", get(control_status))
        .route("/control/liquidate", post(control_liquidate))
        .route("/paper/portfolio", get(paper_portfolio))
        .route("/paper/mark", post(paper_mark))
        .route("/paper/equity_curve", get(paper_equity_curve))
        .route("/paper/equity_agg", get(paper_equity_agg))
        .route("/paper/alpha", post(paper_alpha))
        .route("/paper/risk_metrics", post(paper_risk_metrics))
        .route("/paper/risk_rolling", post(paper_risk_rolling))
        .route("/paper/factor_regression", post(paper_factor_regression))
        .route("/paper/factor_regression_nw", post(paper_factor_regression_nw))
        .route("/paper/factor_regression_nw_auto", post(paper_factor_regression_nw_auto))
        .route("/paper/factor_regression_qs", post(paper_factor_regression_qs))
        .route("/paper/factor_regression_qs_aic", post(paper_factor_regression_qs_aic))
        .route("/paper/factor_regression_qs_var", post(paper_factor_regression_qs_var))
        .route("/risk/alert-check", post(risk_alert_check))
        .with_state(state);

    let port = std::env::var("RISK_ENGINE_PORT").unwrap_or_else(|_| "3001".into());
    let addr = format!("0.0.0.0:{port}");
    let listener = tokio::net::TcpListener::bind(&addr).await.unwrap();
    tracing::info!("risk-engine listening on {addr}");

    // graceful shutdown — SIGINT(Ctrl+C) / SIGTERM 수신 시 최종 스냅샷 저장 후 종료.
    let shutdown = async move {
        let ctrl_c = tokio::signal::ctrl_c();
        #[cfg(unix)]
        let sigterm = async {
            tokio::signal::unix::signal(tokio::signal::unix::SignalKind::terminate())
                .expect("SIGTERM handler")
                .recv()
                .await;
        };
        #[cfg(not(unix))]
        let sigterm = std::future::pending::<()>();
        tokio::select! {
            _ = ctrl_c => tracing::info!("SIGINT — graceful shutdown"),
            _ = sigterm => tracing::info!("SIGTERM — graceful shutdown"),
        }
        if no_db {
            let snap = with_book(|b| b.to_snapshot());
            paper_db::save_snapshot(&snap);
            tracing::info!("final snapshot saved on shutdown");
        }
    };
    axum::serve(listener, app).with_graceful_shutdown(shutdown).await.unwrap();
}

async fn health() -> Json<serde_json::Value> {
    let env = std::env::var("ENV").unwrap_or_else(|_| "local".into());
    Json(json!({ "status": "ok", "service": "risk-engine", "env": env }))
}

/// F4 리스크 판정.
async fn risk_check(Json(req): Json<RiskRequest>) -> Json<serde_json::Value> {
    Json(json!(evaluate(&req)))
}

/// Phase B-2: 시장경보/공매도 포함 리스크 판정. /risk/check 와 동일 로직, 명시적 경로.
async fn risk_alert_check(Json(req): Json<RiskRequest>) -> Json<serde_json::Value> {
    Json(json!(evaluate(&req)))
}

/// 계정 추출 — ?account=... 쿼리, 미지정 시 기본 계정.
fn acct(q: &std::collections::HashMap<String, String>) -> String {
    q.get("account").cloned().unwrap_or_else(|| DEFAULT_ACCOUNT.to_string())
}

/// 등록된 가상 계정 목록.
async fn paper_accounts() -> Json<serde_json::Value> {
    Json(json!({ "accounts": list_accounts() }))
}

/// F5 가상 체결 — DB-우선 durability(원자성). 영속화 성공 후에만 인메모리 원장 commit.
/// DB 미설정 시 인메모리 단독. DB 설정 + insert 실패 시 원장 미변경 + 5xx(BOOK/DB 불일치 방지).
async fn paper_execute(
    State(state): State<AppState>,
    axum::extract::Query(q): axum::extract::Query<std::collections::HashMap<String, String>>,
    Json(order): Json<OrderRequest>,
) -> (StatusCode, Json<serde_json::Value>) {
    let account = acct(&q);
    // DB durability 는 기본 계정만(명명 계정은 인메모리 격리 — paper_fills 계정 미구분).
    let persist = account == DEFAULT_ACCOUNT;

    // 0) F6.3 긴급 중지(halt) — 신규 주문 차단. 청산(/control/liquidate)은 별도 경로로 계속 가능.
    if with_account_book(&account, |book| book.is_halted()) {
        let position = with_account_book(&account, |book| book.pos(&order.ticker));
        let result = json!({
            "accepted": false, "fill": serde_json::Value::Null,
            "position": position, "reason": "거래 중지(halt) — 신규 주문 차단",
        });
        return (StatusCode::OK, Json(result));
    }

    // 1) 준비 — 검증 + 체결 계산만(원장 미변경, 멱등키 조회 포함).
    let prepared = with_account_book(&account, |book| book.prepare(&order));
    let (fill, position) = match prepared {
        Prepared::Duplicate(prev) => {
            let position = with_account_book(&account, |book| book.pos(&prev.ticker));
            let result = json!({
                "accepted": true, "fill": prev, "position": position,
                "reason": "중복 주문(멱등키) — 기존 체결 반환",
            });
            return (StatusCode::OK, Json(result));
        }
        Prepared::Rejected(reason) => {
            let position = with_account_book(&account, |book| book.pos(&order.ticker));
            let result = json!({
                "accepted": false, "fill": serde_json::Value::Null,
                "position": position, "reason": reason,
            });
            return (StatusCode::OK, Json(result));
        }
        Prepared::Accepted { fill, position } => (fill, position),
    };

    // 2) DB durability 우선(기본 계정만). 실패 → 원장 미변경 + 5xx. 충돌(0행) → 동시 중복으로 간주, commit 생략.
    if persist {
        if let Some(pool) = &state.pool {
            match paper_db::insert_fill(pool, &fill).await {
                Ok(0) => {
                    let position = with_account_book(&account, |book| book.pos(&fill.ticker));
                    let result = json!({
                        "accepted": true, "fill": fill, "position": position,
                        "reason": "중복 주문(멱등키, DB) — 재체결 없음",
                    });
                    return (StatusCode::OK, Json(result));
                }
                Ok(_) => {}
                Err(e) => {
                    tracing::error!("paper_fills insert failed, rejecting order: {e}");
                    let result = json!({
                        "accepted": false, "fill": serde_json::Value::Null,
                        "position": with_account_book(&account, |book| book.pos(&fill.ticker)),
                        "reason": "원장 영속화 실패 — 체결 취소(원장 미변경)",
                    });
                    return (StatusCode::INTERNAL_SERVER_ERROR, Json(result));
                }
            }
        }
    }

    // 3) DB 성공(또는 미설정/명명 계정) → 인메모리 원장 commit.
    let result = with_account_book(&account, |book| book.commit(&fill, &position));
    // postgres 없을 때 JSON 스냅샷 저장(기본 계정만) — 동기 호출로 SIGINT 전 완료 보장.
    if persist && state.pool.is_none() {
        let snap = with_account_book(&account, |book| book.to_snapshot());
        paper_db::save_snapshot(&snap);
    }
    (StatusCode::OK, Json(json!(result)))
}

/// F6.3 긴급 중지(kill-switch) 설정 — {halted: bool}, ?account=. true 면 신규 주문 차단.
async fn control_halt(
    axum::extract::Query(q): axum::extract::Query<std::collections::HashMap<String, String>>,
    Json(req): Json<serde_json::Value>,
) -> Json<serde_json::Value> {
    let account = acct(&q);
    let halt = req.get("halted").and_then(|v| v.as_bool()).unwrap_or(true);
    with_account_book(&account, |book| book.set_halt(halt));
    tracing::warn!("control: halt[{account}] set to {halt}");
    Json(json!({ "account": account, "halted": halt }))
}

/// F6.3 제어 상태 — 중지 여부 + 보유 종목 수(?account=).
async fn control_status(
    axum::extract::Query(q): axum::extract::Query<std::collections::HashMap<String, String>>,
) -> Json<serde_json::Value> {
    let account = acct(&q);
    let (halted, open) = with_account_book(&account, |book| (book.is_halted(), book.open_positions().len()));
    Json(json!({ "account": account, "halted": halted, "open_positions": open }))
}

/// F6.3 긴급 청산 — {prices:{ticker:price}}, ?account= 로 보유 전 종목 시장가 매도 + 자동 halt.
/// Fail-Safe: 인메모리 원장 권위, DB 영속화는 기본 계정 best-effort(실패 시 warn).
async fn control_liquidate(
    State(state): State<AppState>,
    axum::extract::Query(q): axum::extract::Query<std::collections::HashMap<String, String>>,
    Json(req): Json<serde_json::Value>,
) -> Json<serde_json::Value> {
    let account = acct(&q);
    let prices: std::collections::HashMap<String, f64> = req
        .get("prices")
        .and_then(|v| v.as_object())
        .map(|m| m.iter().filter_map(|(k, v)| v.as_f64().map(|p| (k.clone(), p))).collect())
        .unwrap_or_default();

    // 청산 + 후속 신규주문 차단(긴급 정지).
    let fills = with_account_book(&account, |book| {
        let f = book.liquidate(&prices);
        book.set_halt(true);
        f
    });

    // best-effort DB 영속화(기본 계정 청산 체결도 거래기록 보존).
    if account == DEFAULT_ACCOUNT {
        if let Some(pool) = &state.pool {
            for fill in &fills {
                if let Err(e) = paper_db::insert_fill(pool, fill).await {
                    tracing::warn!("liquidate fill persist failed: {e}");
                }
            }
        }
    }

    let realized: f64 = fills.iter().map(|f| f.realized_pnl).sum();
    tracing::warn!("control: liquidated[{account}] {} positions, realized {realized}", fills.len());
    Json(json!({ "account": account, "liquidated": fills.len(), "fills": fills, "realized_pnl": realized, "halted": true }))
}

/// 가상 포트폴리오 — 종목별 포지션 + 실현손익 + 체결 건수(?account=).
async fn paper_portfolio(
    axum::extract::Query(q): axum::extract::Query<std::collections::HashMap<String, String>>,
) -> Json<serde_json::Value> {
    let account = acct(&q);
    let snapshot = with_account_book(&account, |book| {
        json!({
            "account": account,
            "positions": book.open_positions(),
            "realized_pnl": book.realized_pnl,
            "realized_by_ticker": book.realized_by_ticker,
            "fills": book.ledger.len(),
            "cash": book.cash,
        })
    });
    Json(snapshot)
}

/// 예수금 직접 설정 — MyPage 예수금 변경 시 paper account cash sync.
/// `cash` 파라미터는 초기(총) 예수금이며, 잔여예수금 = initial_cash - Σcost_basis 로 계산.
async fn paper_set_cash(
    State(state): State<AppState>,
    axum::extract::Query(q): axum::extract::Query<std::collections::HashMap<String, String>>,
    Json(body): Json<serde_json::Value>,
) -> Json<serde_json::Value> {
    let account = acct(&q);
    let initial_cash = body.get("cash").and_then(|v| v.as_f64()).unwrap_or(0.0);
    let new_cash = with_account_book(&account, |book| {
        let cost_basis: f64 = book.positions.values().map(|p| p.cost_basis).sum();
        book.cash = (initial_cash - cost_basis).max(0.0);
        book.cash
    });
    if account == DEFAULT_ACCOUNT && state.pool.is_none() {
        let snap = with_account_book(&account, |book| book.to_snapshot());
        paper_db::save_snapshot(&snap);
    }
    Json(json!({ "ok": true, "account": account, "cash": new_cash }))
}

/// mark-to-market — 현재가 맵 입력 → 종목별 미실현 + 손익곡선 점 추가(+DB).
async fn paper_mark(
    State(state): State<AppState>,
    Json(prices): Json<std::collections::HashMap<String, f64>>,
) -> Json<serde_json::Value> {
    let ts = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_secs() as i64)
        .unwrap_or(0);
    let (point, snapshot) = with_book(|book| {
        let point = book.mark(&prices, ts);
        let snap = json!({
            "ts": point.ts,
            "realized": point.realized,
            "unrealized": point.unrealized,
            "equity": point.equity,
            "unrealized_by_ticker": book.unrealized_by_ticker(&prices),
        });
        (point, snap)
    });
    if let Some(pool) = &state.pool {
        if let Err(e) = paper_db::insert_equity(pool, &point).await {
            tracing::warn!("paper_equity insert failed: {e}");
        }
    }
    Json(snapshot)
}

/// 손익곡선 — mark 호출 누적 시계열(raw).
async fn paper_equity_curve() -> Json<serde_json::Value> {
    let curve = with_book(|book| json!(book.equity_curve));
    Json(curve)
}

/// 손익곡선 기간 집계 — ?period=daily|weekly (기본 daily).
async fn paper_equity_agg(
    axum::extract::Query(q): axum::extract::Query<std::collections::HashMap<String, String>>,
) -> Json<serde_json::Value> {
    let period = q.get("period").map(|s| s.as_str()).unwrap_or("daily");
    let buckets = with_book(|book| match period {
        "weekly" => json!(book.aggregate(604_800)),
        "monthly" => json!(book.aggregate_calendar("month")),
        "quarterly" => json!(book.aggregate_calendar("quarter")),
        _ => json!(book.aggregate(86_400)),
    });
    Json(buckets)
}

/// 벤치마크 대비 알파 — {initial_capital, benchmark:[..]}.
async fn paper_alpha(Json(req): Json<serde_json::Value>) -> Json<serde_json::Value> {
    let cap = req.get("initial_capital").and_then(|v| v.as_f64()).unwrap_or(10_000_000.0);
    let bench: Vec<f64> = req
        .get("benchmark")
        .and_then(|v| v.as_array())
        .map(|a| a.iter().filter_map(|x| x.as_f64()).collect())
        .unwrap_or_default();
    let (port, b, alpha) = with_book(|book| book.alpha(cap, &bench));
    Json(json!({ "portfolio_return": port, "benchmark_return": b, "alpha": alpha }))
}

/// 위험조정 성과 — {initial_capital, benchmark:[..]} → beta·정보비율·트래킹에러.
async fn paper_risk_metrics(Json(req): Json<serde_json::Value>) -> Json<serde_json::Value> {
    let cap = req.get("initial_capital").and_then(|v| v.as_f64()).unwrap_or(10_000_000.0);
    let bench: Vec<f64> = req
        .get("benchmark")
        .and_then(|v| v.as_array())
        .map(|a| a.iter().filter_map(|x| x.as_f64()).collect())
        .unwrap_or_default();
    let (beta, ir, te) = with_book(|book| book.risk_metrics(cap, &bench));
    Json(json!({ "beta": beta, "information_ratio": ir, "tracking_error": te }))
}

fn f64_vec(req: &serde_json::Value, key: &str) -> Vec<f64> {
    req.get(key)
        .and_then(|v| v.as_array())
        .map(|a| a.iter().filter_map(|x| x.as_f64()).collect())
        .unwrap_or_default()
}

/// 롤링 위험지표 — {initial_capital, benchmark:[..], window}.
async fn paper_risk_rolling(Json(req): Json<serde_json::Value>) -> Json<serde_json::Value> {
    let cap = req.get("initial_capital").and_then(|v| v.as_f64()).unwrap_or(10_000_000.0);
    let bench = f64_vec(&req, "benchmark");
    let window = req.get("window").and_then(|v| v.as_u64()).unwrap_or(20) as usize;
    let rolling = with_book(|book| {
        book.risk_metrics_rolling(cap, &bench, window)
            .into_iter()
            .map(|(b, ir, te)| json!({ "beta": b, "information_ratio": ir, "tracking_error": te }))
            .collect::<Vec<_>>()
    });
    Json(json!(rolling))
}

/// Fama-French 다요인 회귀 — {initial_capital, factors:[[..],[..],..]}.
async fn paper_factor_regression(Json(req): Json<serde_json::Value>) -> Json<serde_json::Value> {
    let cap = req.get("initial_capital").and_then(|v| v.as_f64()).unwrap_or(10_000_000.0);
    let factors: Vec<Vec<f64>> = req
        .get("factors")
        .and_then(|v| v.as_array())
        .map(|a| {
            a.iter()
                .map(|f| f.as_array().map(|fa| fa.iter().filter_map(|x| x.as_f64()).collect()).unwrap_or_default())
                .collect()
        })
        .unwrap_or_default();
    let result = with_book(|book| book.factor_regression(cap, &factors));
    match result {
        Some((alpha, betas)) => Json(json!({ "alpha": alpha, "betas": betas })),
        None => Json(json!({ "error": "singular or length mismatch" })),
    }
}

/// Fama-French OLS + Newey-West HAC SE — {initial_capital, factors:[..], lag}.
async fn paper_factor_regression_nw(Json(req): Json<serde_json::Value>) -> Json<serde_json::Value> {
    let cap = req.get("initial_capital").and_then(|v| v.as_f64()).unwrap_or(10_000_000.0);
    let lag = req.get("lag").and_then(|v| v.as_u64()).unwrap_or(0) as usize;
    let factors: Vec<Vec<f64>> = req
        .get("factors")
        .and_then(|v| v.as_array())
        .map(|a| {
            a.iter()
                .map(|f| f.as_array().map(|fa| fa.iter().filter_map(|x| x.as_f64()).collect()).unwrap_or_default())
                .collect()
        })
        .unwrap_or_default();
    let result = with_book(|book| book.factor_regression_nw(cap, &factors, lag));
    match result {
        Some((alpha, betas, se)) => Json(json!({ "alpha": alpha, "betas": betas, "std_errors": se, "lag": lag })),
        None => Json(json!({ "error": "singular or length mismatch" })),
    }
}

/// Andrews 자동 대역폭 NW — {initial_capital, factors:[..]}. lag 자동 선택.
async fn paper_factor_regression_nw_auto(Json(req): Json<serde_json::Value>) -> Json<serde_json::Value> {
    let cap = req.get("initial_capital").and_then(|v| v.as_f64()).unwrap_or(10_000_000.0);
    let factors: Vec<Vec<f64>> = req
        .get("factors")
        .and_then(|v| v.as_array())
        .map(|a| {
            a.iter()
                .map(|f| f.as_array().map(|fa| fa.iter().filter_map(|x| x.as_f64()).collect()).unwrap_or_default())
                .collect()
        })
        .unwrap_or_default();
    let result = with_book(|book| book.factor_regression_nw_auto(cap, &factors));
    match result {
        Some((alpha, betas, se, lag)) => {
            Json(json!({ "alpha": alpha, "betas": betas, "std_errors": se, "lag_auto": lag }))
        }
        None => Json(json!({ "error": "singular or length mismatch" })),
    }
}

/// QS 커널 HAC + VAR(1) prewhiten — {initial_capital, factors:[..], bandwidth?, prewhiten?}.
async fn paper_factor_regression_qs(Json(req): Json<serde_json::Value>) -> Json<serde_json::Value> {
    let cap = req.get("initial_capital").and_then(|v| v.as_f64()).unwrap_or(10_000_000.0);
    let bw = req.get("bandwidth").and_then(|v| v.as_f64()).unwrap_or(0.0);
    let pw = req.get("prewhiten").and_then(|v| v.as_bool()).unwrap_or(true);
    let full = req.get("full_var").and_then(|v| v.as_bool()).unwrap_or(false);
    let factors: Vec<Vec<f64>> = req
        .get("factors")
        .and_then(|v| v.as_array())
        .map(|a| {
            a.iter()
                .map(|f| f.as_array().map(|fa| fa.iter().filter_map(|x| x.as_f64()).collect()).unwrap_or_default())
                .collect()
        })
        .unwrap_or_default();
    let result = with_book(|book| book.factor_regression_qs_full(cap, &factors, bw, pw, full));
    match result {
        Some((alpha, betas, se)) => Json(json!({
            "alpha": alpha, "betas": betas, "std_errors": se,
            "kernel": "qs", "prewhiten": pw, "full_var": full
        })),
        None => Json(json!({ "error": "singular or length mismatch" })),
    }
}

/// QS HAC + AIC 차수선택 prewhitening — {initial_capital, factors:[..], max_order?}.
async fn paper_factor_regression_qs_aic(Json(req): Json<serde_json::Value>) -> Json<serde_json::Value> {
    let cap = req.get("initial_capital").and_then(|v| v.as_f64()).unwrap_or(10_000_000.0);
    let maxo = req.get("max_order").and_then(|v| v.as_u64()).unwrap_or(5) as usize;
    let factors: Vec<Vec<f64>> = req
        .get("factors")
        .and_then(|v| v.as_array())
        .map(|a| {
            a.iter()
                .map(|f| f.as_array().map(|fa| fa.iter().filter_map(|x| x.as_f64()).collect()).unwrap_or_default())
                .collect()
        })
        .unwrap_or_default();
    let result = with_book(|book| book.factor_regression_qs_aic(cap, &factors, maxo));
    match result {
        Some((alpha, betas, se, p)) => Json(json!({
            "alpha": alpha, "betas": betas, "std_errors": se, "kernel": "qs", "ar_order": p
        })),
        None => Json(json!({ "error": "singular or length mismatch" })),
    }
}

/// QS HAC + full VAR(p) prewhitening, IC 차수선택 — {..., max_order?, criterion?(aic|bic|hq)}.
async fn paper_factor_regression_qs_var(Json(req): Json<serde_json::Value>) -> Json<serde_json::Value> {
    let cap = req.get("initial_capital").and_then(|v| v.as_f64()).unwrap_or(10_000_000.0);
    let maxo = req.get("max_order").and_then(|v| v.as_u64()).unwrap_or(3) as usize;
    let crit = req.get("criterion").and_then(|v| v.as_str()).unwrap_or("bic").to_string();
    let stab = req.get("stabilize").and_then(|v| v.as_bool()).unwrap_or(false);
    let comp = req.get("companion").and_then(|v| v.as_bool()).unwrap_or(false);
    let factors: Vec<Vec<f64>> = req
        .get("factors")
        .and_then(|v| v.as_array())
        .map(|a| {
            a.iter()
                .map(|f| f.as_array().map(|fa| fa.iter().filter_map(|x| x.as_f64()).collect()).unwrap_or_default())
                .collect()
        })
        .unwrap_or_default();
    let result = with_book(|book| book.factor_regression_qs_var_full(cap, &factors, maxo, &crit, stab, comp));
    match result {
        Some((alpha, betas, se, p)) => Json(json!({
            "alpha": alpha, "betas": betas, "std_errors": se,
            "kernel": "qs", "var_order": p, "criterion": crit, "stabilize": stab, "companion": comp
        })),
        None => Json(json!({ "error": "singular or length mismatch" })),
    }
}
