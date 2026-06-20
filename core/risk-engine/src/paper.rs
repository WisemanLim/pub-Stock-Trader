//! F5 가상(시뮬레이션) 체결 — 실거래 아님. paper-trading 추적 (다종목).
//! 주문 → 슬리피지 반영 체결 → append-only 원장 → 종목별 포지션·실현/미실현 P&L.
//! 감사: 모든 체결 불변 기록(전자금융거래법 §22 거래기록 보존 정신).
//! 영속화: DATABASE_URL 설정 시 postgres paper_fills 테이블 동기화(paper_db).

use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::sync::Mutex;

const SLIPPAGE_BPS: f64 = 0.0; // 페이퍼 트레이딩: 화면 가격 그대로 체결(슬리피지 0)
const FEE_BPS: f64 = 1.5; // 0.015% 수수료
const INITIAL_CASH: f64 = 100_000_000.0; // 시뮬레이션 초기 예수금 1억원

#[derive(Debug, Clone, Deserialize)]
pub struct OrderRequest {
    pub ticker: String,
    pub side: String, // "buy" | "sell"
    pub quantity: f64,
    pub price: f64, // 기준 시장가
    #[serde(default)]
    pub client_order_id: Option<String>, // 멱등키 — 동일 ID 재전송 시 1회만 체결(COMPLIANCE §4.1)
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Fill {
    pub ticker: String,
    pub side: String,
    pub quantity: f64,
    pub fill_price: f64, // 슬리피지 반영
    pub fee: f64,
    pub realized_pnl: f64, // 매도 시 실현손익
    #[serde(default)]
    pub client_order_id: Option<String>, // 멱등키(있으면) — 원장·DB 중복 방지 키
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct Position {
    pub ticker: String,
    pub quantity: f64,
    pub avg_price: f64,
    pub cost_basis: f64, // 실제 매수총금액 = Σ(체결가 × 수량), 매도 시 비례 차감
}

#[derive(Debug, Serialize)]
pub struct OrderResult {
    pub accepted: bool,
    pub fill: Option<Fill>,
    pub position: Position,
    pub reason: String,
}

/// 체결 준비 결과 — DB durability 전 단계. Accepted 만 commit 으로 원장 반영.
#[derive(Debug, Clone)]
pub enum Prepared {
    Duplicate(Fill),                              // 멱등키 재전송 — 기존 체결(commit 불필요)
    Rejected(String),                             // 검증 실패
    Accepted { fill: Fill, position: Position },  // 체결 가능 — DB 영속화 후 commit 대기
}

/// 손익곡선 한 점 — mark-to-market 시점 스냅샷.
#[derive(Debug, Clone, Serialize)]
pub struct EquityPoint {
    pub ts: i64, // epoch seconds
    pub realized: f64,
    pub unrealized: f64,
    pub equity: f64, // realized + unrealized
}

/// 기간 집계 버킷 (일/주).
#[derive(Debug, Clone, Serialize)]
pub struct EquityBucket {
    pub bucket: i64,    // 버킷 시작 epoch(초)
    pub open: f64,
    pub close: f64,
    pub high: f64,
    pub low: f64,
    pub points: usize,
}

/// 가상 포트폴리오 — 다종목. HashMap<ticker, Position>.
#[derive(Default)]
pub struct PaperBook {
    pub positions: HashMap<String, Position>,
    pub realized_pnl: f64,                          // 전체 실현손익(합계)
    pub realized_by_ticker: HashMap<String, f64>,   // 종목별 실현손익
    pub ledger: Vec<Fill>,
    pub equity_curve: Vec<EquityPoint>,             // mark 호출마다 누적
    pub applied_orders: HashMap<String, Fill>,      // client_order_id → 체결(멱등 재전송 방어)
    pub halted: bool,                               // F6.3 긴급 중지(kill-switch) — true 면 신규 주문 차단
    pub cash: f64,                                  // 시뮬레이션 예수금 (매수: 차감, 매도: 가산)
}

/// 재시작 영속화용 스냅샷 — 체결 이력 제외, 핵심 상태만.
#[derive(Serialize, Deserialize, Default)]
pub struct PaperBookSnapshot {
    pub positions: HashMap<String, Position>,
    pub cash: f64,
    pub realized_pnl: f64,
    pub realized_by_ticker: HashMap<String, f64>,
    pub applied_orders: HashMap<String, Fill>,
    pub halted: bool,
}

impl PaperBook {
    pub fn new() -> Self {
        let mut b = Self::default();
        b.cash = INITIAL_CASH;
        b
    }

    pub fn to_snapshot(&self) -> PaperBookSnapshot {
        PaperBookSnapshot {
            positions: self.positions.clone(),
            cash: self.cash,
            realized_pnl: self.realized_pnl,
            realized_by_ticker: self.realized_by_ticker.clone(),
            applied_orders: self.applied_orders.clone(),
            halted: self.halted,
        }
    }

    pub fn restore_from_snapshot(&mut self, snap: PaperBookSnapshot) {
        self.positions = snap.positions;
        self.cash = snap.cash;
        self.realized_pnl = snap.realized_pnl;
        self.realized_by_ticker = snap.realized_by_ticker;
        self.applied_orders = snap.applied_orders;
        self.halted = snap.halted;
    }

    pub fn pos(&self, ticker: &str) -> Position {
        self.positions.get(ticker).cloned().unwrap_or_else(|| Position {
            ticker: ticker.to_string(),
            quantity: 0.0,
            avg_price: 0.0,
            cost_basis: 0.0,
        })
    }

    /// 체결 준비 — 검증 + 체결가/수수료/포지션 계산만(상태 미변경).
    /// DB durability 후 `commit` 으로 원장 반영(원자성: DB 실패 시 원장 미변경).
    pub fn prepare(&self, order: &OrderRequest) -> Prepared {
        // 멱등키 — 동일 client_order_id 재전송 시 기존 체결 반환(재체결 없음).
        if let Some(coid) = &order.client_order_id {
            if let Some(prev) = self.applied_orders.get(coid) {
                return Prepared::Duplicate(prev.clone());
            }
        }
        if order.quantity <= 0.0 {
            return Prepared::Rejected("수량은 양수여야 함".into());
        }
        let slip = SLIPPAGE_BPS / 10_000.0;
        let fee_rate = FEE_BPS / 10_000.0;
        let mut p = self.pos(&order.ticker);

        match order.side.as_str() {
            "buy" => {
                let fill_price = order.price * (1.0 + slip);
                let fee = fill_price * order.quantity * fee_rate;
                let prev_cost = p.quantity * p.avg_price;
                let new_qty = p.quantity + order.quantity;
                // 매수 수수료를 취득원가에 포함: avg_price = (기존원가 + 체결금액 + 수수료) / 신규수량
                p.avg_price = (prev_cost + fill_price * order.quantity + fee) / new_qty;
                p.quantity = new_qty;
                p.cost_basis += fill_price * order.quantity + fee;
                let fill = Fill {
                    ticker: order.ticker.clone(),
                    side: "buy".into(),
                    quantity: order.quantity,
                    fill_price,
                    fee,
                    realized_pnl: 0.0,
                    client_order_id: order.client_order_id.clone(),
                };
                Prepared::Accepted { fill, position: p }
            }
            "sell" => {
                if order.quantity > p.quantity {
                    return Prepared::Rejected("보유 수량 초과 매도 불가".into());
                }
                let fill_price = order.price * (1.0 - slip);
                let fee = fill_price * order.quantity * fee_rate;
                let realized = (fill_price - p.avg_price) * order.quantity - fee;
                let old_qty = p.quantity;
                p.quantity -= order.quantity;
                if p.quantity <= 1e-9 {
                    p.quantity = 0.0;
                    p.avg_price = 0.0;
                    p.cost_basis = 0.0;
                } else {
                    p.cost_basis *= p.quantity / old_qty;
                }
                let fill = Fill {
                    ticker: order.ticker.clone(),
                    side: "sell".into(),
                    quantity: order.quantity,
                    fill_price,
                    fee,
                    realized_pnl: realized,
                    client_order_id: order.client_order_id.clone(),
                };
                Prepared::Accepted { fill, position: p }
            }
            _ => Prepared::Rejected("side 는 buy|sell".into()),
        }
    }

    /// prepare 결과를 원장에 반영(positions/realized/ledger/멱등맵). DB 영속화 성공 후 호출.
    pub fn commit(&mut self, fill: &Fill, position: &Position) -> OrderResult {
        self.positions.insert(fill.ticker.clone(), position.clone());
        // 예수금 정산: 매수 → 차감(비용+수수료), 매도 → 가산(대금-수수료)
        if fill.side == "buy" {
            self.cash -= fill.fill_price * fill.quantity + fill.fee;
        } else if fill.side == "sell" {
            self.cash += fill.fill_price * fill.quantity - fill.fee;
            self.realized_pnl += fill.realized_pnl;
            *self.realized_by_ticker.entry(fill.ticker.clone()).or_insert(0.0) += fill.realized_pnl;
        }
        self.ledger.push(fill.clone());
        self.record_idempotent(fill);
        self.accept(fill.clone(), position.clone())
    }

    /// 시장가 모의 체결 — 준비+반영 일괄(비-DB 경로·하이드레이션·테스트).
    pub fn execute(&mut self, order: &OrderRequest) -> OrderResult {
        match self.prepare(order) {
            Prepared::Duplicate(prev) => {
                let position = self.pos(&prev.ticker);
                OrderResult {
                    accepted: true,
                    fill: Some(prev),
                    position,
                    reason: "중복 주문(멱등키) — 기존 체결 반환".into(),
                }
            }
            Prepared::Rejected(reason) => self.reject(&order.ticker, &reason),
            Prepared::Accepted { fill, position } => self.commit(&fill, &position),
        }
    }

    /// 원장 리플레이로 상태 복원(DB 하이드레이션용). 실현손익 미반영 단순 재구성.
    pub fn replay(&mut self, fills: &[Fill]) {
        for f in fills {
            let order = OrderRequest {
                ticker: f.ticker.clone(),
                side: f.side.clone(),
                quantity: f.quantity,
                price: if f.side == "buy" {
                    f.fill_price / (1.0 + SLIPPAGE_BPS / 10_000.0)
                } else {
                    f.fill_price / (1.0 - SLIPPAGE_BPS / 10_000.0)
                },
                client_order_id: f.client_order_id.clone(), // 멱등키 보존(하이드레이션)
            };
            self.execute(&order);
        }
    }

    /// 종목 현재가 기준 미실현 손익.
    pub fn unrealized_pnl(&self, ticker: &str, mark_price: f64) -> f64 {
        let p = self.pos(ticker);
        if p.quantity == 0.0 {
            return 0.0;
        }
        (mark_price - p.avg_price) * p.quantity
    }

    /// 보유 종목(수량>0) 목록.
    pub fn open_positions(&self) -> Vec<Position> {
        self.positions.values().filter(|p| p.quantity > 0.0).cloned().collect()
    }

    // ── F6.3 긴급 제어(원격 kill-switch / 청산) ──

    /// 거래 중지(halt) 설정 — true 면 paper_execute 신규 주문 차단(긴급 봇 중지).
    pub fn set_halt(&mut self, halt: bool) {
        self.halted = halt;
    }

    pub fn is_halted(&self) -> bool {
        self.halted
    }

    /// 긴급 청산 — 보유 전 종목을 현재가(prices)로 시장가 매도. 가격 없는 종목은 보류.
    /// halt 와 독립 실행(중지 상태에서도 청산 가능). 반환: 청산 체결 목록.
    pub fn liquidate(&mut self, prices: &HashMap<String, f64>) -> Vec<Fill> {
        let mut fills = Vec::new();
        // 보유 목록 스냅샷 후 순차 매도(execute 가 positions 변경 → 사전 수집).
        let open: Vec<(String, f64)> = self
            .open_positions()
            .iter()
            .map(|p| (p.ticker.clone(), p.quantity))
            .collect();
        for (ticker, qty) in open {
            if let Some(&price) = prices.get(&ticker) {
                let order = OrderRequest {
                    ticker,
                    side: "sell".into(),
                    quantity: qty,
                    price,
                    client_order_id: None,
                };
                if let Some(f) = self.execute(&order).fill {
                    fills.push(f);
                }
            }
        }
        fills
    }

    /// 종목별 실현손익.
    pub fn realized_for(&self, ticker: &str) -> f64 {
        self.realized_by_ticker.get(ticker).copied().unwrap_or(0.0)
    }

    /// 종목별 미실현 손익 (현재가 맵 기준). 가격 없는 종목은 제외.
    pub fn unrealized_by_ticker(&self, prices: &HashMap<String, f64>) -> HashMap<String, f64> {
        let mut out = HashMap::new();
        for (ticker, p) in &self.positions {
            if p.quantity <= 0.0 {
                continue;
            }
            if let Some(&mark) = prices.get(ticker) {
                out.insert(ticker.clone(), (mark - p.avg_price) * p.quantity);
            }
        }
        out
    }

    /// mark-to-market — 손익곡선에 점 추가하고 스냅샷 반환. ts=epoch seconds.
    pub fn mark(&mut self, prices: &HashMap<String, f64>, ts: i64) -> EquityPoint {
        let unreal: f64 = self.unrealized_by_ticker(prices).values().sum();
        let point = EquityPoint {
            ts,
            realized: self.realized_pnl,
            unrealized: unreal,
            equity: self.realized_pnl + unreal,
        };
        self.equity_curve.push(point.clone());
        point
    }

    /// 손익곡선 기간 집계 — period_secs(일=86400, 주=604800) 버킷별 OHLC.
    pub fn aggregate(&self, period_secs: i64) -> Vec<EquityBucket> {
        let p = if period_secs <= 0 { 86400 } else { period_secs };
        self._aggregate_by(|ts| (ts / p) * p)
    }

    /// 달력 집계 — "month"(버킷=YYYYMM) / "quarter"(버킷=YYYYQ).
    pub fn aggregate_calendar(&self, period: &str) -> Vec<EquityBucket> {
        match period {
            "quarter" => self._aggregate_by(|ts| {
                let (y, m) = epoch_to_ym(ts);
                let q = (m - 1) / 3 + 1;
                y * 10 + q as i64 // YYYYQ
            }),
            _ => self._aggregate_by(|ts| {
                let (y, m) = epoch_to_ym(ts);
                y * 100 + m as i64 // YYYYMM
            }),
        }
    }

    fn _aggregate_by<F: Fn(i64) -> i64>(&self, key_fn: F) -> Vec<EquityBucket> {
        let mut buckets: Vec<EquityBucket> = Vec::new();
        for pt in &self.equity_curve {
            let b = key_fn(pt.ts);
            match buckets.last_mut() {
                Some(last) if last.bucket == b => {
                    last.close = pt.equity;
                    last.high = last.high.max(pt.equity);
                    last.low = last.low.min(pt.equity);
                    last.points += 1;
                }
                _ => buckets.push(EquityBucket {
                    bucket: b,
                    open: pt.equity,
                    close: pt.equity,
                    high: pt.equity,
                    low: pt.equity,
                    points: 1,
                }),
            }
        }
        buckets
    }

    /// 벤치마크 대비 초과수익(알파). port_return = Δequity/초기자본,
    /// bench_return = (마지막-처음)/처음. alpha = port - bench.
    pub fn alpha(&self, initial_capital: f64, benchmark: &[f64]) -> (f64, f64, f64) {
        if self.equity_curve.len() < 2 || benchmark.len() < 2 || initial_capital == 0.0 {
            return (0.0, 0.0, 0.0);
        }
        let eq_first = self.equity_curve.first().unwrap().equity;
        let eq_last = self.equity_curve.last().unwrap().equity;
        let port_return = (eq_last - eq_first) / initial_capital;
        let b0 = benchmark[0];
        let bench_return = if b0 != 0.0 {
            (benchmark[benchmark.len() - 1] - b0) / b0
        } else {
            0.0
        };
        (port_return, bench_return, port_return - bench_return)
    }

    /// 위험조정 성과 — 포트 수익률 vs 벤치마크 수익률 시계열로 산출.
    /// 반환 (beta, information_ratio, tracking_error). 길이 부족·분산 0 시 0.
    /// 포트 일별수익률 = Δequity_i / initial_capital. 벤치 = Δbench/bench[i-1].
    pub fn risk_metrics(&self, initial_capital: f64, benchmark: &[f64]) -> (f64, f64, f64) {
        let n = self.equity_curve.len();
        if n < 3 || benchmark.len() != n || initial_capital == 0.0 {
            return (0.0, 0.0, 0.0);
        }
        let port_r = self.port_returns(initial_capital);
        let mut bench_r = Vec::with_capacity(n - 1);
        for i in 1..n {
            let b0 = benchmark[i - 1];
            bench_r.push(if b0 != 0.0 { (benchmark[i] - b0) / b0 } else { 0.0 });
        }
        metrics_from_returns(&port_r, &bench_r)
    }

    /// 포트 일별 수익률 시계열 (Δequity / 초기자본).
    pub fn port_returns(&self, initial_capital: f64) -> Vec<f64> {
        let n = self.equity_curve.len();
        if n < 2 || initial_capital == 0.0 {
            return Vec::new();
        }
        (1..n)
            .map(|i| (self.equity_curve[i].equity - self.equity_curve[i - 1].equity) / initial_capital)
            .collect()
    }

    /// 롤링 윈도우 위험지표 — 각 윈도우별 (beta, ir, te). 윈도우 부족 시 빈 벡터.
    pub fn risk_metrics_rolling(
        &self,
        initial_capital: f64,
        benchmark: &[f64],
        window: usize,
    ) -> Vec<(f64, f64, f64)> {
        let n = self.equity_curve.len();
        if window < 3 || benchmark.len() != n || n < window {
            return Vec::new();
        }
        let port = self.port_returns(initial_capital); // 길이 n-1
        let mut bench_r = Vec::with_capacity(n - 1);
        for i in 1..n {
            let b0 = benchmark[i - 1];
            bench_r.push(if b0 != 0.0 { (benchmark[i] - b0) / b0 } else { 0.0 });
        }
        let w = window - 1; // 수익률 윈도우 길이
        let mut out = Vec::new();
        for start in 0..=(port.len().saturating_sub(w)) {
            let p = &port[start..start + w];
            let b = &bench_r[start..start + w];
            out.push(metrics_from_returns(p, b));
        }
        out
    }

    /// Fama-French 다요인 OLS — port_excess ~ α + Σ βᵢ·factorᵢ.
    /// factors: 각 길이 == port_returns 길이. 반환 (alpha, [betas]). 특이행렬·길이불일치 시 None.
    pub fn factor_regression(
        &self,
        initial_capital: f64,
        factors: &[Vec<f64>],
    ) -> Option<(f64, Vec<f64>)> {
        let y = self.port_returns(initial_capital);
        let n = y.len();
        let k = factors.len();
        if n < k + 2 || factors.iter().any(|f| f.len() != n) {
            return None;
        }
        // 설계행렬 X: n x (k+1), 첫 열=1(절편)
        let cols = k + 1;
        let mut xtx = vec![vec![0.0; cols]; cols];
        let mut xty = vec![0.0; cols];
        for i in 0..n {
            let mut row = vec![1.0; cols];
            for j in 0..k {
                row[j + 1] = factors[j][i];
            }
            for a in 0..cols {
                xty[a] += row[a] * y[i];
                for b in 0..cols {
                    xtx[a][b] += row[a] * row[b];
                }
            }
        }
        let coef = solve_linear(xtx, xty)?;
        Some((coef[0], coef[1..].to_vec()))
    }

    /// Fama-French OLS + Newey-West HAC 표준오차. lag=Bartlett 커널 시차.
    /// 반환 (alpha, [betas], [std_errors]). 길이=k+1(절편 포함). 특이/길이불일치 None.
    pub fn factor_regression_nw(
        &self,
        initial_capital: f64,
        factors: &[Vec<f64>],
        lag: usize,
    ) -> Option<(f64, Vec<f64>, Vec<f64>)> {
        let y = self.port_returns(initial_capital);
        let n = y.len();
        let k = factors.len();
        if n < k + 2 || factors.iter().any(|f| f.len() != n) {
            return None;
        }
        let cols = k + 1;
        // 설계행렬 X (n x cols)
        let x: Vec<Vec<f64>> = (0..n)
            .map(|i| {
                let mut row = vec![1.0; cols];
                for j in 0..k {
                    row[j + 1] = factors[j][i];
                }
                row
            })
            .collect();
        // X'X, X'y
        let mut xtx = vec![vec![0.0; cols]; cols];
        let mut xty = vec![0.0; cols];
        for i in 0..n {
            for a in 0..cols {
                xty[a] += x[i][a] * y[i];
                for b in 0..cols {
                    xtx[a][b] += x[i][a] * x[i][b];
                }
            }
        }
        let coef = solve_linear(xtx.clone(), xty)?;
        let bread = invert(&xtx)?; // (X'X)^-1

        // 잔차
        let resid: Vec<f64> = (0..n)
            .map(|i| y[i] - (0..cols).map(|a| x[i][a] * coef[a]).sum::<f64>())
            .collect();

        // Newey-West meat: S = Σ_l w_l Σ_t x_t x_{t-l}' (e_t e_{t-l}), Bartlett w_l=1-l/(L+1)
        let mut meat = vec![vec![0.0; cols]; cols];
        for l in 0..=lag {
            let w = if lag == 0 { 1.0 } else { 1.0 - l as f64 / (lag as f64 + 1.0) };
            let mut gamma = vec![vec![0.0; cols]; cols];
            for t in l..n {
                let ee = resid[t] * resid[t - l];
                for a in 0..cols {
                    for b in 0..cols {
                        gamma[a][b] += x[t][a] * x[t - l][b] * ee;
                    }
                }
            }
            for a in 0..cols {
                for b in 0..cols {
                    let add = if l == 0 { gamma[a][b] } else { gamma[a][b] + gamma[b][a] };
                    meat[a][b] += w * add;
                }
            }
        }
        // var = bread * meat * bread
        let bm = matmul(&bread, &meat);
        let cov = matmul(&bm, &bread);
        let se: Vec<f64> = (0..cols).map(|i| cov[i][i].max(0.0).sqrt()).collect();
        Some((coef[0], coef[1..].to_vec(), se))
    }

    /// 회귀 잔차 (OLS) — Andrews 대역폭 추정용.
    fn _residuals(&self, initial_capital: f64, factors: &[Vec<f64>]) -> Option<Vec<f64>> {
        let (alpha, betas) = self.factor_regression(initial_capital, factors)?;
        let y = self.port_returns(initial_capital);
        Some(
            (0..y.len())
                .map(|i| {
                    let pred = alpha + (0..betas.len()).map(|j| betas[j] * factors[j][i]).sum::<f64>();
                    y[i] - pred
                })
                .collect(),
        )
    }

    /// Andrews(1991) 자동 대역폭 NW — 잔차 AR(1)로 최적 Bartlett lag 추정 후 NW 적용.
    /// 반환 (alpha, [betas], [std_errors], lag_used).
    pub fn factor_regression_nw_auto(
        &self,
        initial_capital: f64,
        factors: &[Vec<f64>],
    ) -> Option<(f64, Vec<f64>, Vec<f64>, usize)> {
        let resid = self._residuals(initial_capital, factors)?;
        let lag = andrews_bandwidth(&resid);
        let (alpha, betas, se) = self.factor_regression_nw(initial_capital, factors, lag)?;
        Some((alpha, betas, se, lag))
    }

    /// QS HAC + AIC 차수선택 대각 AR(p) prewhitening.
    /// 잔차로 AR(p*) 차수를 AIC 로 선택 후 모멘트 성분별 AR(p*) 백색화.
    /// 반환 (alpha, [betas], [std_errors], p_selected).
    pub fn factor_regression_qs_aic(
        &self,
        initial_capital: f64,
        factors: &[Vec<f64>],
        max_order: usize,
    ) -> Option<(f64, Vec<f64>, Vec<f64>, usize)> {
        let y = self.port_returns(initial_capital);
        let n = y.len();
        let k = factors.len();
        if n < k + 2 || factors.iter().any(|f| f.len() != n) {
            return None;
        }
        let cols = k + 1;
        let x: Vec<Vec<f64>> = (0..n)
            .map(|i| {
                let mut row = vec![1.0; cols];
                for j in 0..k {
                    row[j + 1] = factors[j][i];
                }
                row
            })
            .collect();
        let mut xtx = vec![vec![0.0; cols]; cols];
        let mut xty = vec![0.0; cols];
        for i in 0..n {
            for a in 0..cols {
                xty[a] += x[i][a] * y[i];
                for b in 0..cols {
                    xtx[a][b] += x[i][a] * x[i][b];
                }
            }
        }
        let coef = solve_linear(xtx.clone(), xty)?;
        let bread = invert(&xtx)?;
        let resid: Vec<f64> = (0..n)
            .map(|i| y[i] - (0..cols).map(|a| x[i][a] * coef[a]).sum::<f64>())
            .collect();

        let p = aic_ar_order(&resid, max_order.min(n / 4));

        let mut g: Vec<Vec<f64>> = (0..n)
            .map(|t| (0..cols).map(|a| x[t][a] * resid[t]).collect())
            .collect();

        // 성분별 AR(p) 계수(OLS) + 백색화 + recolor 인자
        let mut recolor = vec![1.0; cols];
        if p >= 1 {
            let mut whitened = g.clone();
            for j in 0..cols {
                let series: Vec<f64> = g.iter().map(|row| row[j]).collect();
                if let Some(phi) = ar_ols(&series, p) {
                    for t in p..n {
                        let pred: f64 = (0..p).map(|l| phi[l] * series[t - 1 - l]).sum();
                        whitened[t][j] = series[t] - pred;
                    }
                    let sphi: f64 = phi.iter().sum();
                    recolor[j] = 1.0 / (1.0 - sphi).max(0.03); // (1-Σφ)^-1, 안정 클램프
                }
            }
            g = whitened[p..].to_vec();
        }

        let m = g.len();
        let bw = 1.3221 * (m as f64).powf(0.2);
        let mut s = vec![vec![0.0; cols]; cols];
        for l in 0..m {
            let w = if l == 0 { 1.0 } else { qs_weight(l as f64 / bw) };
            if w.abs() < 1e-10 {
                continue;
            }
            let mut gamma = vec![vec![0.0; cols]; cols];
            for t in l..m {
                for pp in 0..cols {
                    for q in 0..cols {
                        gamma[pp][q] += g[t][pp] * g[t - l][q];
                    }
                }
            }
            for pp in 0..cols {
                for q in 0..cols {
                    let add = if l == 0 { gamma[pp][q] } else { gamma[pp][q] + gamma[q][pp] };
                    s[pp][q] += w * add;
                }
            }
        }
        if p >= 1 {
            for pp in 0..cols {
                for q in 0..cols {
                    s[pp][q] *= recolor[pp] * recolor[q];
                }
            }
        }
        let bm = matmul(&bread, &s);
        let cov = matmul(&bm, &bread);
        let se: Vec<f64> = (0..cols).map(|i| cov[i][i].max(0.0).sqrt()).collect();
        Some((coef[0], coef[1..].to_vec(), se, p))
    }

    /// QS HAC + full VAR(p) prewhitening, 차수 IC 선택(aic|bic|hq).
    /// 반환 (alpha, [betas], [std_errors], p_selected).
    pub fn factor_regression_qs_var(
        &self,
        initial_capital: f64,
        factors: &[Vec<f64>],
        max_order: usize,
        criterion: &str,
    ) -> Option<(f64, Vec<f64>, Vec<f64>, usize)> {
        self.factor_regression_qs_var_opt(initial_capital, factors, max_order, criterion, false)
    }

    /// qs_var + stabilize(ΣA 반경 기반 안정성 사영).
    pub fn factor_regression_qs_var_opt(
        &self,
        initial_capital: f64,
        factors: &[Vec<f64>],
        max_order: usize,
        criterion: &str,
        stabilize: bool,
    ) -> Option<(f64, Vec<f64>, Vec<f64>, usize)> {
        self.factor_regression_qs_var_full(initial_capital, factors, max_order, criterion, stabilize, false)
    }

    /// qs_var + stabilize + companion(true 시 companion 고유값 반경 기반 사영, p>1 정확).
    pub fn factor_regression_qs_var_full(
        &self,
        initial_capital: f64,
        factors: &[Vec<f64>],
        max_order: usize,
        criterion: &str,
        stabilize: bool,
        companion: bool,
    ) -> Option<(f64, Vec<f64>, Vec<f64>, usize)> {
        let y = self.port_returns(initial_capital);
        let n = y.len();
        let k = factors.len();
        if n < k + 2 || factors.iter().any(|f| f.len() != n) {
            return None;
        }
        let cols = k + 1;
        let x: Vec<Vec<f64>> = (0..n)
            .map(|i| {
                let mut row = vec![1.0; cols];
                for j in 0..k {
                    row[j + 1] = factors[j][i];
                }
                row
            })
            .collect();
        let mut xtx = vec![vec![0.0; cols]; cols];
        let mut xty = vec![0.0; cols];
        for i in 0..n {
            for a in 0..cols {
                xty[a] += x[i][a] * y[i];
                for b in 0..cols {
                    xtx[a][b] += x[i][a] * x[i][b];
                }
            }
        }
        let coef = solve_linear(xtx.clone(), xty)?;
        let bread = invert(&xtx)?;
        let resid: Vec<f64> = (0..n)
            .map(|i| y[i] - (0..cols).map(|a| x[i][a] * coef[a]).sum::<f64>())
            .collect();

        let g0: Vec<Vec<f64>> = (0..n)
            .map(|t| (0..cols).map(|a| x[t][a] * resid[t]).collect())
            .collect();

        let p = var_order_select(&g0, max_order.min(n / (2 * cols + 2)).max(0), criterion);

        let mut g = g0.clone();
        let mut sum_a: Option<Vec<Vec<f64>>> = None;
        if p >= 1 {
            if let Some((mut a_list, _whitened)) = var_fit(&g0, p) {
                // ΣA_l
                let sum_of = |al: &Vec<Vec<Vec<f64>>>| {
                    let mut s = vec![vec![0.0; cols]; cols];
                    for m in al {
                        for r in 0..cols {
                            for c in 0..cols {
                                s[r][c] += m[r][c];
                            }
                        }
                    }
                    s
                };
                // 안정성 사영 — companion(정확, p>1) 또는 ΣA 스펙트럴 반경 ≥0.97 시 전 계수 축소
                if stabilize {
                    let radius = if companion {
                        companion_radius_qr(&a_list, cols, p)  // QR 고유값(복소 정확)
                    } else {
                        spectral_radius(&sum_of(&a_list), 100)
                    };
                    let sc = if radius >= 0.97 && radius > 0.0 { 0.97 / radius } else { 1.0 };
                    if sc < 1.0 {
                        for m in a_list.iter_mut() {
                            for r in 0..cols {
                                for c in 0..cols {
                                    m[r][c] *= sc;
                                }
                            }
                        }
                    }
                }
                // (스케일된) 계수로 잔차 재계산
                let mut wh = vec![vec![0.0; cols]; n];
                for t in p..n {
                    for eq in 0..cols {
                        let mut pred = 0.0;
                        for l in 0..p {
                            for c in 0..cols {
                                pred += a_list[l][eq][c] * g0[t - 1 - l][c];
                            }
                        }
                        wh[t][eq] = g0[t][eq] - pred;
                    }
                }
                g = wh[p..].to_vec();
                sum_a = Some(sum_of(&a_list));
            }
        }

        let m = g.len();
        let bw = 1.3221 * (m as f64).powf(0.2);
        let mut s = vec![vec![0.0; cols]; cols];
        for l in 0..m {
            let w = if l == 0 { 1.0 } else { qs_weight(l as f64 / bw) };
            if w.abs() < 1e-10 {
                continue;
            }
            let mut gamma = vec![vec![0.0; cols]; cols];
            for t in l..m {
                for pp in 0..cols {
                    for q in 0..cols {
                        gamma[pp][q] += g[t][pp] * g[t - l][q];
                    }
                }
            }
            for pp in 0..cols {
                for q in 0..cols {
                    let add = if l == 0 { gamma[pp][q] } else { gamma[pp][q] + gamma[q][pp] };
                    s[pp][q] += w * add;
                }
            }
        }
        // recolor D=(I-ΣA)^-1, S=D S* D'
        if let Some(a) = &sum_a {
            let mut im = vec![vec![0.0; cols]; cols];
            for r in 0..cols {
                for c in 0..cols {
                    im[r][c] = (if r == c { 1.0 } else { 0.0 }) - a[r][c];
                }
            }
            if let Some(d) = invert(&im) {
                let ds = matmul(&d, &s);
                let dt: Vec<Vec<f64>> = (0..cols).map(|i| (0..cols).map(|j| d[j][i]).collect()).collect();
                s = matmul(&ds, &dt);
            }
        }
        let bm = matmul(&bread, &s);
        let cov = matmul(&bm, &bread);
        let se: Vec<f64> = (0..cols).map(|i| cov[i][i].max(0.0).sqrt()).collect();
        Some((coef[0], coef[1..].to_vec(), se, p))
    }

    /// QS(Quadratic Spectral) 커널 HAC + 선택적 VAR(1) prewhitening.
    /// prewhiten=true: full=false → 대각 AR(1), full=true → full VAR(1) 행렬.
    /// 반환 (alpha, [betas], [std_errors]).
    pub fn factor_regression_qs(
        &self,
        initial_capital: f64,
        factors: &[Vec<f64>],
        bandwidth: f64,
        prewhiten: bool,
    ) -> Option<(f64, Vec<f64>, Vec<f64>)> {
        self.factor_regression_qs_full(initial_capital, factors, bandwidth, prewhiten, false)
    }

    /// QS HAC + prewhitening (full=true → full VAR(1) 행렬 사전백색화).
    pub fn factor_regression_qs_full(
        &self,
        initial_capital: f64,
        factors: &[Vec<f64>],
        bandwidth: f64,
        prewhiten: bool,
        full_var: bool,
    ) -> Option<(f64, Vec<f64>, Vec<f64>)> {
        let y = self.port_returns(initial_capital);
        let n = y.len();
        let k = factors.len();
        if n < k + 2 || factors.iter().any(|f| f.len() != n) {
            return None;
        }
        let cols = k + 1;
        let x: Vec<Vec<f64>> = (0..n)
            .map(|i| {
                let mut row = vec![1.0; cols];
                for j in 0..k {
                    row[j + 1] = factors[j][i];
                }
                row
            })
            .collect();
        let mut xtx = vec![vec![0.0; cols]; cols];
        let mut xty = vec![0.0; cols];
        for i in 0..n {
            for a in 0..cols {
                xty[a] += x[i][a] * y[i];
                for b in 0..cols {
                    xtx[a][b] += x[i][a] * x[i][b];
                }
            }
        }
        let coef = solve_linear(xtx.clone(), xty)?;
        let bread = invert(&xtx)?;
        let resid: Vec<f64> = (0..n)
            .map(|i| y[i] - (0..cols).map(|a| x[i][a] * coef[a]).sum::<f64>())
            .collect();

        // 모멘트 g_t = x_t · e_t  (n × cols)
        let mut g: Vec<Vec<f64>> = (0..n)
            .map(|t| (0..cols).map(|a| x[t][a] * resid[t]).collect())
            .collect();

        // VAR(1) prewhitening — 대각 AR(1) 또는 full VAR(1) 행렬.
        let mut a_diag = vec![0.0; cols];       // 대각 모드 계수
        let mut a_mat: Option<Vec<Vec<f64>>> = None;  // full 모드 행렬 A
        if prewhiten && full_var {
            // A = M0·M1^-1, M0=Σg_t g_{t-1}', M1=Σg_{t-1}g_{t-1}'
            let mut m0 = vec![vec![0.0; cols]; cols];
            let mut m1 = vec![vec![0.0; cols]; cols];
            for t in 1..n {
                for p in 0..cols {
                    for q in 0..cols {
                        m0[p][q] += g[t][p] * g[t - 1][q];
                        m1[p][q] += g[t - 1][p] * g[t - 1][q];
                    }
                }
            }
            if let Some(m1inv) = invert(&m1) {
                let a = matmul(&m0, &m1inv);
                let mut gw = vec![vec![0.0; cols]; n];
                for t in 1..n {
                    for p in 0..cols {
                        gw[t][p] = g[t][p] - (0..cols).map(|q| a[p][q] * g[t - 1][q]).sum::<f64>();
                    }
                }
                g = gw[1..].to_vec();
                a_mat = Some(a);
            }
        } else if prewhiten {
            for j in 0..cols {
                let mut num = 0.0;
                let mut den = 0.0;
                for t in 1..n {
                    num += g[t][j] * g[t - 1][j];
                    den += g[t - 1][j] * g[t - 1][j];
                }
                a_diag[j] = if den > 0.0 { (num / den).clamp(-0.97, 0.97) } else { 0.0 };
            }
            let mut gw = vec![vec![0.0; cols]; n];
            for t in 1..n {
                for j in 0..cols {
                    gw[t][j] = g[t][j] - a_diag[j] * g[t - 1][j];
                }
            }
            g = gw[1..].to_vec();
        }

        let m = g.len();
        let bw = if bandwidth > 0.0 { bandwidth } else { 1.3221 * (m as f64).powf(0.2) };

        // S* = Σ_l qs(l/bw) Σ_t g_t g_{t-l}'  (l=0 가중1, 대칭)
        let mut s = vec![vec![0.0; cols]; cols];
        for l in 0..m {
            let w = if l == 0 { 1.0 } else { qs_weight(l as f64 / bw) };
            if w.abs() < 1e-10 {
                continue;
            }
            let mut gamma = vec![vec![0.0; cols]; cols];
            for t in l..m {
                for p in 0..cols {
                    for q in 0..cols {
                        gamma[p][q] += g[t][p] * g[t - l][q];
                    }
                }
            }
            for p in 0..cols {
                for q in 0..cols {
                    let add = if l == 0 { gamma[p][q] } else { gamma[p][q] + gamma[q][p] };
                    s[p][q] += w * add;
                }
            }
        }

        // recolor: D = (I - A)^-1, S = D S* D'
        if let Some(a) = &a_mat {
            // full: I - A 역행렬
            let mut im = vec![vec![0.0; cols]; cols];
            for p in 0..cols {
                for q in 0..cols {
                    im[p][q] = (if p == q { 1.0 } else { 0.0 }) - a[p][q];
                }
            }
            if let Some(d) = invert(&im) {
                let ds = matmul(&d, &s);
                let dt: Vec<Vec<f64>> = (0..cols).map(|i| (0..cols).map(|j| d[j][i]).collect()).collect();
                s = matmul(&ds, &dt);
            }
        } else if prewhiten {
            for p in 0..cols {
                for q in 0..cols {
                    s[p][q] /= (1.0 - a_diag[p]) * (1.0 - a_diag[q]);
                }
            }
        }

        let bm = matmul(&bread, &s);
        let cov = matmul(&bm, &bread);
        let se: Vec<f64> = (0..cols).map(|i| cov[i][i].max(0.0).sqrt()).collect();
        Some((coef[0], coef[1..].to_vec(), se))
    }

    /// 멱등키 보유 체결을 applied_orders 에 등록(재전송 시 재체결 차단).
    fn record_idempotent(&mut self, fill: &Fill) {
        if let Some(coid) = &fill.client_order_id {
            self.applied_orders.insert(coid.clone(), fill.clone());
        }
    }

    fn accept(&self, fill: Fill, position: Position) -> OrderResult {
        OrderResult {
            accepted: true,
            fill: Some(fill),
            position,
            reason: "체결 완료(가상)".into(),
        }
    }

    fn reject(&self, ticker: &str, reason: &str) -> OrderResult {
        OrderResult {
            accepted: false,
            fill: None,
            position: self.pos(ticker),
            reason: reason.into(),
        }
    }
}

/// epoch seconds → (year, month). Howard Hinnant civil_from_days 알고리즘.
fn epoch_to_ym(ts: i64) -> (i64, u32) {
    let days = ts.div_euclid(86_400);
    let z = days + 719_468;
    let era = if z >= 0 { z } else { z - 146_096 } / 146_097;
    let doe = z - era * 146_097;
    let yoe = (doe - doe / 1460 + doe / 36_524 - doe / 146_096) / 365;
    let y = yoe + era * 400;
    let doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    let mp = (5 * doy + 2) / 153;
    let m = if mp < 10 { mp + 3 } else { mp - 9 };
    let year = if m <= 2 { y + 1 } else { y };
    (year, m as u32)
}

/// 두 수익률 시계열 → (beta, information_ratio, tracking_error).
fn metrics_from_returns(port: &[f64], bench: &[f64]) -> (f64, f64, f64) {
    let m = port.len() as f64;
    if m < 2.0 || port.len() != bench.len() {
        return (0.0, 0.0, 0.0);
    }
    let mean = |v: &[f64]| v.iter().sum::<f64>() / m;
    let pm = mean(port);
    let bm = mean(bench);
    let mut cov = 0.0;
    let mut var_b = 0.0;
    for i in 0..port.len() {
        cov += (port[i] - pm) * (bench[i] - bm);
        var_b += (bench[i] - bm).powi(2);
    }
    cov /= m;
    var_b /= m;
    let beta = if var_b > 0.0 { cov / var_b } else { 0.0 };
    let active: Vec<f64> = port.iter().zip(bench).map(|(p, b)| p - b).collect();
    let am = mean(&active);
    let te = (active.iter().map(|x| (x - am).powi(2)).sum::<f64>() / m).sqrt();
    let ir = if te > 0.0 { am / te } else { 0.0 };
    (beta, ir, te)
}

/// 선형계 Ax=b 해 (Gauss-Jordan, 소규모). 특이행렬 시 None.
fn solve_linear(mut a: Vec<Vec<f64>>, mut b: Vec<f64>) -> Option<Vec<f64>> {
    let n = b.len();
    for col in 0..n {
        // 부분 피벗
        let mut piv = col;
        for r in (col + 1)..n {
            if a[r][col].abs() > a[piv][col].abs() {
                piv = r;
            }
        }
        if a[piv][col].abs() < 1e-12 {
            return None;
        }
        a.swap(col, piv);
        b.swap(col, piv);
        let d = a[col][col];
        for j in 0..n {
            a[col][j] /= d;
        }
        b[col] /= d;
        for r in 0..n {
            if r != col {
                let f = a[r][col];
                for j in 0..n {
                    a[r][j] -= f * a[col][j];
                }
                b[r] -= f * b[col];
            }
        }
    }
    Some(b)
}

/// Andrews(1991) Bartlett 커널 자동 대역폭 — 잔차 AR(1) ρ 기반.
/// S_T = 1.1447·(α(1)·T)^(1/3), α(1)=4ρ²/((1-ρ)²(1+ρ)²). lag=floor(S_T).
fn andrews_bandwidth(resid: &[f64]) -> usize {
    let t = resid.len();
    if t < 4 {
        return 0;
    }
    // AR(1) ρ = Σe_t·e_{t-1} / Σe_t²
    let mut num = 0.0;
    let mut den = 0.0;
    for i in 1..t {
        num += resid[i] * resid[i - 1];
        den += resid[i - 1] * resid[i - 1];
    }
    if den <= 0.0 {
        return 0;
    }
    let rho = (num / den).clamp(-0.97, 0.97);
    let a1 = 4.0 * rho * rho / ((1.0 - rho).powi(2) * (1.0 + rho).powi(2));
    let st = 1.1447 * (a1 * t as f64).powf(1.0 / 3.0);
    let lag = st.floor() as i64;
    lag.clamp(0, (t as i64) - 1) as usize
}

/// 정방행렬 행렬식 (Gaussian elimination). 특이 ≈0.
fn det(a: &[Vec<f64>]) -> f64 {
    let n = a.len();
    let mut m: Vec<Vec<f64>> = a.iter().map(|r| r.clone()).collect();
    let mut d = 1.0;
    for col in 0..n {
        let mut piv = col;
        for r in (col + 1)..n {
            if m[r][col].abs() > m[piv][col].abs() {
                piv = r;
            }
        }
        if m[piv][col].abs() < 1e-15 {
            return 0.0;
        }
        if piv != col {
            m.swap(col, piv);
            d = -d;
        }
        d *= m[col][col];
        for r in (col + 1)..n {
            let f = m[r][col] / m[col][col];
            for j in col..n {
                m[r][j] -= f * m[col][j];
            }
        }
    }
    d
}

/// full VAR(p) 적합 — 반환 (A_l 계수행렬[p][cols][cols], 잔차[n-p][cols]).
fn var_fit(g: &[Vec<f64>], p: usize) -> Option<(Vec<Vec<Vec<f64>>>, Vec<Vec<f64>>)> {
    let n = g.len();
    let cols = g[0].len();
    if p == 0 || n <= p + cols * p {
        return None;
    }
    let nreg = p * cols;
    // 방정식별 OLS — X 공통, y만 다름. XtX 공통 계산.
    let mut xtx = vec![vec![0.0; nreg]; nreg];
    let mut xty = vec![vec![0.0; cols]; nreg]; // [reg][eq]
    for t in p..n {
        let mut xrow = vec![0.0; nreg];
        for l in 0..p {
            for c in 0..cols {
                xrow[l * cols + c] = g[t - 1 - l][c];
            }
        }
        for a in 0..nreg {
            for j in 0..cols {
                xty[a][j] += xrow[a] * g[t][j];
            }
            for b in 0..nreg {
                xtx[a][b] += xrow[a] * xrow[b];
            }
        }
    }
    let xtx_inv = invert(&xtx)?;
    // coef[reg][eq]
    let mut coef = vec![vec![0.0; cols]; nreg];
    for j in 0..cols {
        let col_xty: Vec<f64> = (0..nreg).map(|a| xty[a][j]).collect();
        for a in 0..nreg {
            coef[a][j] = (0..nreg).map(|b| xtx_inv[a][b] * col_xty[b]).sum();
        }
    }
    // A_l[l][eq][var]
    let mut a_list = vec![vec![vec![0.0; cols]; cols]; p];
    for l in 0..p {
        for eq in 0..cols {
            for c in 0..cols {
                a_list[l][eq][c] = coef[l * cols + c][eq];
            }
        }
    }
    // 잔차
    let mut resid = Vec::with_capacity(n - p);
    for t in p..n {
        let mut e = vec![0.0; cols];
        for eq in 0..cols {
            let mut pred = 0.0;
            for l in 0..p {
                for c in 0..cols {
                    pred += a_list[l][eq][c] * g[t - 1 - l][c];
                }
            }
            e[eq] = g[t][eq] - pred;
        }
        resid.push(e);
    }
    Some((a_list, resid))
}

/// VAR 잔차 공분산 행렬식.
fn resid_cov_det(resid: &[Vec<f64>], cols: usize) -> f64 {
    let m = resid.len();
    if m < 2 {
        return 0.0;
    }
    let mean: Vec<f64> = (0..cols).map(|j| resid.iter().map(|r| r[j]).sum::<f64>() / m as f64).collect();
    let mut cov = vec![vec![0.0; cols]; cols];
    for r in resid {
        for a in 0..cols {
            for b in 0..cols {
                cov[a][b] += (r[a] - mean[a]) * (r[b] - mean[b]);
            }
        }
    }
    for a in 0..cols {
        for b in 0..cols {
            cov[a][b] /= m as f64;
        }
    }
    det(&cov)
}

/// VAR 차수선택 — criterion="aic"|"bic"|"hq". 잔차 공분산 det 기반 IC 최소 p.
fn var_order_select(g: &[Vec<f64>], max_p: usize, criterion: &str) -> usize {
    let n = g.len();
    let cols = g[0].len();
    if n < 2 * cols + 4 || max_p == 0 {
        return 0;
    }
    let mut best_p = 0;
    let mut best_ic = f64::INFINITY;
    // p=0: 동시 잔차 공분산
    let det0 = resid_cov_det(g, cols);
    if det0 > 0.0 {
        best_ic = (n as f64) * det0.ln();
    }
    for p in 1..=max_p {
        let Some((_, resid)) = var_fit(g, p) else { continue };
        let d = resid_cov_det(&resid, cols);
        if d <= 0.0 {
            continue;
        }
        let neff = resid.len() as f64;
        let params = (cols * cols * p) as f64;
        let pen = match criterion {
            "bic" => neff.ln() * params,
            "hq" => 2.0 * neff.ln().ln().max(0.0) * params,
            _ => 2.0 * params, // aic
        };
        let ic = neff * d.ln() + pen;
        if ic < best_ic {
            best_ic = ic;
            best_p = p;
        }
    }
    best_p
}

/// 행렬 스펙트럴 반경(최대 고유값 절댓값) — 거듭제곱 반복 근사.
fn spectral_radius(a: &[Vec<f64>], iters: usize) -> f64 {
    let n = a.len();
    if n == 0 {
        return 0.0;
    }
    let mut v = vec![1.0 / (n as f64).sqrt(); n];
    let mut lambda = 0.0;
    for _ in 0..iters {
        let mut w = vec![0.0; n];
        for i in 0..n {
            for j in 0..n {
                w[i] += a[i][j] * v[j];
            }
        }
        let norm = w.iter().map(|x| x * x).sum::<f64>().sqrt();
        if norm < 1e-15 {
            return 0.0;
        }
        for i in 0..n {
            v[i] = w[i] / norm;
        }
        lambda = norm;
    }
    lambda
}

/// VAR(p) companion 행렬 구성 — (cols·p)×(cols·p). 상단블록=[A_1..A_p], 하단=I 시프트.
fn build_companion(a_list: &[Vec<Vec<f64>>], cols: usize, p: usize) -> Vec<Vec<f64>> {
    let mp = cols * p;
    let mut c = vec![vec![0.0; mp]; mp];
    // 상단 cols 행: A_1 | A_2 | ... | A_p
    for l in 0..p {
        for r in 0..cols {
            for cc in 0..cols {
                c[r][l * cols + cc] = a_list[l][r][cc];
            }
        }
    }
    // 하단: 항등 시프트 (블록 부대각)
    for i in cols..mp {
        c[i][i - cols] = 1.0;
    }
    c
}

/// companion 스펙트럴 반경 — 개별 고유값 사영용(power iteration, p>1 정확).
fn companion_radius(a_list: &[Vec<Vec<f64>>], cols: usize, p: usize) -> f64 {
    spectral_radius(&build_companion(a_list, cols, p), 300)
}

/// QR 알고리즘 고유값 크기 — 실 Schur(이동 QR), 2x2 블록=복소켤레쌍 처리.
/// 반환 각 고유값 |λ| 목록(복소 포함). 비대칭 행렬용.
fn qr_eigen_magnitudes(a: &[Vec<f64>]) -> Vec<f64> {
    let n = a.len();
    if n == 0 {
        return vec![];
    }
    let mut h: Vec<Vec<f64>> = a.iter().map(|r| r.clone()).collect();
    // 비이동 QR 반복 (Gram-Schmidt QR). 소규모 행렬용, 수렴까지 다수 반복.
    for _ in 0..500 {
        let (q, r) = qr_decompose(&h);
        h = matmul(&r, &q); // RQ → 다음 반복
        // 수렴 판정: 부대각 합 작아지면 종료
        let mut off = 0.0;
        for i in 1..n {
            off += h[i][i - 1].abs();
        }
        if off < 1e-9 {
            break;
        }
    }
    // 실 Schur: 대각 또는 2x2 블록 → 고유값 크기
    let mut mags = Vec::with_capacity(n);
    let mut i = 0;
    while i < n {
        let sub = if i + 1 < n { h[i + 1][i].abs() } else { 0.0 };
        if sub > 1e-6 && i + 1 < n {
            // 2x2 블록 [[a,b],[c,d]] → 고유값 크기
            let (aa, bb, cc, dd) = (h[i][i], h[i][i + 1], h[i + 1][i], h[i + 1][i + 1]);
            let tr = aa + dd;
            let det = aa * dd - bb * cc;
            let disc = tr * tr - 4.0 * det;
            if disc < 0.0 {
                // 복소켤레: |λ| = sqrt(det)
                let m = det.abs().sqrt();
                mags.push(m);
                mags.push(m);
            } else {
                let s = disc.sqrt();
                mags.push(((tr + s) / 2.0).abs());
                mags.push(((tr - s) / 2.0).abs());
            }
            i += 2;
        } else {
            mags.push(h[i][i].abs());
            i += 1;
        }
    }
    mags
}

/// Gram-Schmidt QR 분해 (소규모). 반환 (Q, R).
fn qr_decompose(a: &[Vec<f64>]) -> (Vec<Vec<f64>>, Vec<Vec<f64>>) {
    let n = a.len();
    // 열벡터
    let mut q = vec![vec![0.0; n]; n];
    let mut r = vec![vec![0.0; n]; n];
    let col = |m: &[Vec<f64>], j: usize| -> Vec<f64> { (0..n).map(|i| m[i][j]).collect() };
    let mut qcols: Vec<Vec<f64>> = Vec::new();
    for j in 0..n {
        let mut v = col(a, j);
        for (k, qk) in qcols.iter().enumerate() {
            let dot: f64 = (0..n).map(|i| qk[i] * a[i][j]).sum();
            r[k][j] = dot;
            for i in 0..n {
                v[i] -= dot * qk[i];
            }
        }
        let norm = v.iter().map(|x| x * x).sum::<f64>().sqrt();
        if norm < 1e-15 {
            qcols.push(vec![0.0; n]);
            r[j][j] = 0.0;
        } else {
            for x in v.iter_mut() {
                *x /= norm;
            }
            r[j][j] = norm;
            qcols.push(v);
        }
    }
    for j in 0..n {
        for i in 0..n {
            q[i][j] = qcols[j][i];
        }
    }
    (q, r)
}

/// companion QR 고유값 기반 정확 스펙트럴 반경(복소 포함).
fn companion_radius_qr(a_list: &[Vec<Vec<f64>>], cols: usize, p: usize) -> f64 {
    let c = build_companion(a_list, cols, p);
    qr_eigen_magnitudes(&c).into_iter().fold(0.0, f64::max)
}

/// VAR 계수합 행렬 안정성 사영 — 스펙트럴 반경 ≥ max_r 시 축소 스케일.
/// 반환 스케일 인자 s (A ← s·A). |λ|<max_r 보장(정상성).
fn stabilize_scale(sum_a: &[Vec<f64>], max_r: f64) -> f64 {
    let r = spectral_radius(sum_a, 100);
    if r >= max_r && r > 0.0 {
        max_r / r
    } else {
        1.0
    }
}

/// Yule-Walker AR(p) — 자기공분산 + Levinson-Durbin 재귀. 실패 시 None.
fn ar_yule_walker(series: &[f64], p: usize) -> Option<Vec<f64>> {
    let n = series.len();
    if p == 0 || n <= p + 1 {
        return None;
    }
    let mean = series.iter().sum::<f64>() / n as f64;
    let x: Vec<f64> = series.iter().map(|v| v - mean).collect();
    // 자기공분산 r[0..=p]
    let mut r = vec![0.0; p + 1];
    for k in 0..=p {
        let mut s = 0.0;
        for t in k..n {
            s += x[t] * x[t - k];
        }
        r[k] = s / n as f64;
    }
    if r[0] <= 0.0 {
        return None;
    }
    // Levinson-Durbin
    let mut phi = vec![0.0; p];
    let mut e = r[0];
    for k in 0..p {
        let mut acc = r[k + 1];
        for j in 0..k {
            acc -= phi[j] * r[k - j];
        }
        let refl = if e.abs() < 1e-15 { 0.0 } else { acc / e };
        let prev: Vec<f64> = phi[..k].to_vec();
        phi[k] = refl;
        for j in 0..k {
            phi[j] = prev[j] - refl * prev[k - 1 - j];
        }
        e *= 1.0 - refl * refl;
        if e <= 0.0 {
            break;
        }
    }
    Some(phi)
}

/// AR(p) OLS 계수 — series 의 p차 자기회귀. 실패 시 None.
fn ar_ols(series: &[f64], p: usize) -> Option<Vec<f64>> {
    let n = series.len();
    if p == 0 || n <= p + 1 {
        return None;
    }
    let rows = n - p;
    // X (rows × p), y (rows)
    let mut xtx = vec![vec![0.0; p]; p];
    let mut xty = vec![0.0; p];
    for t in p..n {
        let yt = series[t];
        for a in 0..p {
            let xa = series[t - 1 - a];
            xty[a] += xa * yt;
            for b in 0..p {
                xtx[a][b] += xa * series[t - 1 - b];
            }
        }
    }
    let _ = rows;
    solve_linear(xtx, xty)
}

/// AIC 기반 AR 차수 선택 — p=0..max_order 중 AIC 최소. AIC=n·ln(σ²)+2(p+1).
fn aic_ar_order(series: &[f64], max_order: usize) -> usize {
    let n = series.len();
    if n < 8 || max_order == 0 {
        return 0;
    }
    let mean = series.iter().sum::<f64>() / n as f64;
    let var0 = series.iter().map(|v| (v - mean).powi(2)).sum::<f64>() / n as f64;
    let mut best_p = 0;
    let mut best_aic = if var0 > 0.0 { n as f64 * var0.ln() + 2.0 } else { f64::INFINITY };
    for p in 1..=max_order {
        let Some(phi) = ar_ols(series, p) else { continue };
        let mut sse = 0.0;
        let mut cnt = 0;
        for t in p..n {
            let pred: f64 = (0..p).map(|l| phi[l] * series[t - 1 - l]).sum();
            sse += (series[t] - pred).powi(2);
            cnt += 1;
        }
        if cnt == 0 {
            continue;
        }
        let sigma2 = sse / cnt as f64;
        if sigma2 <= 0.0 {
            continue;
        }
        let aic = cnt as f64 * sigma2.ln() + 2.0 * (p as f64 + 1.0);
        if aic < best_aic {
            best_aic = aic;
            best_p = p;
        }
    }
    best_p
}

/// Quadratic Spectral 커널 가중 — w(x)=25/(12π²x²)·(sin(6πx/5)/(6πx/5) - cos(6πx/5)).
fn qs_weight(x: f64) -> f64 {
    if x.abs() < 1e-12 {
        return 1.0;
    }
    let d = 6.0 * std::f64::consts::PI * x / 5.0;
    let pre = 25.0 / (12.0 * std::f64::consts::PI.powi(2) * x * x);
    pre * (d.sin() / d - d.cos())
}

/// 정방행렬 역행렬 (Gauss-Jordan, 소규모). 특이 시 None.
fn invert(a: &[Vec<f64>]) -> Option<Vec<Vec<f64>>> {
    let n = a.len();
    let mut m: Vec<Vec<f64>> = (0..n)
        .map(|i| {
            let mut row = a[i].clone();
            let mut ident = vec![0.0; n];
            ident[i] = 1.0;
            row.extend(ident);
            row
        })
        .collect();
    for col in 0..n {
        let mut piv = col;
        for r in (col + 1)..n {
            if m[r][col].abs() > m[piv][col].abs() {
                piv = r;
            }
        }
        if m[piv][col].abs() < 1e-12 {
            return None;
        }
        m.swap(col, piv);
        let d = m[col][col];
        for j in 0..2 * n {
            m[col][j] /= d;
        }
        for r in 0..n {
            if r != col {
                let f = m[r][col];
                for j in 0..2 * n {
                    m[r][j] -= f * m[col][j];
                }
            }
        }
    }
    Some(m.iter().map(|row| row[n..].to_vec()).collect())
}

/// 행렬 곱 A(p×q)·B(q×r).
fn matmul(a: &[Vec<f64>], b: &[Vec<f64>]) -> Vec<Vec<f64>> {
    let p = a.len();
    let q = b.len();
    let r = b[0].len();
    let mut out = vec![vec![0.0; r]; p];
    for i in 0..p {
        for k in 0..q {
            for j in 0..r {
                out[i][j] += a[i][k] * b[k][j];
            }
        }
    }
    out
}

/// 프로세스 전역 가상 원장 — 계정별 다중화(account_id → PaperBook).
/// 기본 계정("default")은 DB 영속화 대상(기존 동작 보존). 명명 계정은 인메모리 격리.
pub static BOOKS: Mutex<Option<HashMap<String, PaperBook>>> = Mutex::new(None);

pub const DEFAULT_ACCOUNT: &str = "default";

/// 계정별 원장 접근 — 신규 계정은 생성. poison 복구(가용성, F4 Fail-Safe).
pub fn with_account_book<F, R>(account: &str, f: F) -> R
where
    F: FnOnce(&mut PaperBook) -> R,
{
    let mut guard = BOOKS.lock().unwrap_or_else(|e| e.into_inner());
    if guard.is_none() {
        *guard = Some(HashMap::new());
    }
    let book = guard.as_mut().unwrap().entry(account.to_string()).or_insert_with(PaperBook::new);
    f(book)
}

/// 기본 계정 원장 접근(하위호환) — 기존 핸들러/하이드레이션 경로.
pub fn with_book<F, R>(f: F) -> R
where
    F: FnOnce(&mut PaperBook) -> R,
{
    with_account_book(DEFAULT_ACCOUNT, f)
}

/// 등록된 계정 목록(정렬).
pub fn list_accounts() -> Vec<String> {
    let guard = BOOKS.lock().unwrap_or_else(|e| e.into_inner());
    guard
        .as_ref()
        .map(|m| {
            let mut v: Vec<String> = m.keys().cloned().collect();
            v.sort();
            v
        })
        .unwrap_or_default()
}

#[cfg(test)]
mod tests {
    use super::*;

    fn order(ticker: &str, side: &str, qty: f64, price: f64) -> OrderRequest {
        OrderRequest {
            ticker: ticker.into(),
            side: side.into(),
            quantity: qty,
            price,
            client_order_id: None,
        }
    }

    fn order_id(ticker: &str, side: &str, qty: f64, price: f64, coid: &str) -> OrderRequest {
        OrderRequest {
            ticker: ticker.into(),
            side: side.into(),
            quantity: qty,
            price,
            client_order_id: Some(coid.into()),
        }
    }

    // ── 멱등키(client_order_id) ──

    #[test]
    fn idempotent_order_executes_once() {
        let mut b = PaperBook::new();
        let r1 = b.execute(&order_id("005930", "buy", 10.0, 70000.0, "coid-1"));
        let r2 = b.execute(&order_id("005930", "buy", 10.0, 70000.0, "coid-1"));
        assert!(r1.accepted && r2.accepted);
        // 재전송은 재체결하지 않음 — 원장 1건, 포지션 10주 유지.
        assert_eq!(b.ledger.len(), 1);
        assert_eq!(b.pos("005930").quantity, 10.0);
        assert!(r2.reason.contains("멱등"));
        // 반환 체결은 최초와 동일.
        assert_eq!(r2.fill.unwrap().fill_price, r1.fill.unwrap().fill_price);
    }

    #[test]
    fn distinct_order_ids_both_execute() {
        let mut b = PaperBook::new();
        b.execute(&order_id("005930", "buy", 5.0, 70000.0, "coid-a"));
        b.execute(&order_id("005930", "buy", 5.0, 70000.0, "coid-b"));
        assert_eq!(b.ledger.len(), 2);
        assert_eq!(b.pos("005930").quantity, 10.0);
    }

    #[test]
    fn no_order_id_not_deduplicated() {
        let mut b = PaperBook::new();
        b.execute(&order("005930", "buy", 5.0, 70000.0));
        b.execute(&order("005930", "buy", 5.0, 70000.0));
        // 키 없는 주문은 멱등 대상 아님 — 둘 다 체결.
        assert_eq!(b.ledger.len(), 2);
        assert!(b.applied_orders.is_empty());
    }

    // ── F6.3 긴급 제어(halt / liquidate) ──

    #[test]
    fn halt_flag_default_false() {
        let b = PaperBook::new();
        assert!(!b.is_halted());
    }

    #[test]
    fn set_halt_toggles() {
        let mut b = PaperBook::new();
        b.set_halt(true);
        assert!(b.is_halted());
        b.set_halt(false);
        assert!(!b.is_halted());
    }

    #[test]
    fn liquidate_sells_all_positions() {
        let mut b = PaperBook::new();
        b.execute(&order("005930", "buy", 10.0, 70000.0));
        b.execute(&order("000660", "buy", 5.0, 120000.0));
        let prices = HashMap::from([
            ("005930".to_string(), 71000.0),
            ("000660".to_string(), 121000.0),
        ]);
        let fills = b.liquidate(&prices);
        assert_eq!(fills.len(), 2);
        assert!(fills.iter().all(|f| f.side == "sell"));
        // 청산 후 보유 0.
        assert_eq!(b.open_positions().len(), 0);
        assert_eq!(b.pos("005930").quantity, 0.0);
    }

    #[test]
    fn liquidate_skips_ticker_without_price() {
        let mut b = PaperBook::new();
        b.execute(&order("005930", "buy", 10.0, 70000.0));
        b.execute(&order("000660", "buy", 5.0, 120000.0));
        // 005930 가격만 제공 → 000660 보유 유지.
        let prices = HashMap::from([("005930".to_string(), 71000.0)]);
        let fills = b.liquidate(&prices);
        assert_eq!(fills.len(), 1);
        assert_eq!(b.pos("005930").quantity, 0.0);
        assert_eq!(b.pos("000660").quantity, 5.0);
    }

    #[test]
    fn liquidate_works_even_when_halted() {
        let mut b = PaperBook::new();
        b.execute(&order("005930", "buy", 10.0, 70000.0));
        b.set_halt(true); // 중지 상태에서도 청산은 가능(Fail-Safe).
        let prices = HashMap::from([("005930".to_string(), 71000.0)]);
        assert_eq!(b.liquidate(&prices).len(), 1);
    }

    #[test]
    fn replay_preserves_idempotency_key() {
        let mut b = PaperBook::new();
        b.execute(&order_id("005930", "buy", 10.0, 70000.0, "coid-x"));
        let fills = b.ledger.clone();
        let mut restored = PaperBook::new();
        restored.replay(&fills);
        // 하이드레이션 후에도 멱등키 등록 → 재전송 방어 유지.
        assert!(restored.applied_orders.contains_key("coid-x"));
        let dup = restored.execute(&order_id("005930", "buy", 10.0, 70000.0, "coid-x"));
        assert!(dup.reason.contains("멱등"));
        assert_eq!(restored.ledger.len(), 1);
    }

    // ── prepare/commit 2단계(DB-우선 durability 원자성) ──

    #[test]
    fn prepare_does_not_mutate_book() {
        let b = PaperBook::new();
        let prepared = b.prepare(&order("005930", "buy", 10.0, 70000.0));
        // 준비만으로는 원장·포지션 미변경(DB 실패 시 롤백 불필요).
        assert!(matches!(prepared, Prepared::Accepted { .. }));
        assert_eq!(b.ledger.len(), 0);
        assert_eq!(b.pos("005930").quantity, 0.0);
        assert!(b.applied_orders.is_empty());
    }

    #[test]
    fn commit_applies_prepared_fill() {
        let mut b = PaperBook::new();
        if let Prepared::Accepted { fill, position } = b.prepare(&order_id("005930", "buy", 10.0, 70000.0, "c1")) {
            let r = b.commit(&fill, &position);
            assert!(r.accepted);
            assert_eq!(b.ledger.len(), 1);
            assert_eq!(b.pos("005930").quantity, 10.0);
            assert!(b.applied_orders.contains_key("c1"));
        } else {
            panic!("expected Accepted");
        }
    }

    #[test]
    fn prepare_then_discard_leaves_book_clean() {
        // DB 실패 시뮬레이션 — prepare 후 commit 생략 → 원장 완전 무변경.
        let mut b = PaperBook::new();
        b.execute(&order("005930", "buy", 5.0, 70000.0)); // 기존 상태
        let before_qty = b.pos("005930").quantity;
        let before_fills = b.ledger.len();
        let _prepared = b.prepare(&order("005930", "buy", 99.0, 70000.0)); // commit 안 함
        assert_eq!(b.pos("005930").quantity, before_qty);
        assert_eq!(b.ledger.len(), before_fills);
    }

    #[test]
    fn prepare_rejects_oversell() {
        let b = PaperBook::new();
        assert!(matches!(b.prepare(&order("005930", "sell", 10.0, 70000.0)), Prepared::Rejected(_)));
    }

    #[test]
    fn prepare_detects_duplicate() {
        let mut b = PaperBook::new();
        b.execute(&order_id("005930", "buy", 10.0, 70000.0, "dup"));
        assert!(matches!(b.prepare(&order_id("005930", "buy", 10.0, 70000.0, "dup")), Prepared::Duplicate(_)));
    }

    // ── Mutex poison 복구 ──

    #[test]
    fn with_book_recovers_from_poison() {
        use std::panic::{catch_unwind, AssertUnwindSafe};
        // 락을 쥔 채 패닉 → BOOK 오염.
        let _ = catch_unwind(AssertUnwindSafe(|| {
            with_book(|b| {
                b.execute(&order("000660", "buy", 1.0, 1000.0));
                panic!("forced panic while holding BOOK");
            })
        }));
        // 오염 이후에도 with_book 은 내부 데이터를 회수해 정상 동작(영구 5xx 아님).
        let qty = with_book(|b| {
            b.execute(&order("000660", "buy", 2.0, 1000.0));
            b.pos("000660").quantity
        });
        // 패닉 전 체결 1주 + 복구 후 2주 = 3주(데이터 보존).
        assert_eq!(qty, 3.0);
    }

    // ── 계정 다중화(multi-account) — 고유 계정명으로 병렬 시험 격리 ──

    #[test]
    fn accounts_are_isolated() {
        with_account_book("acct-iso-A", |b| {
            b.execute(&order("005930", "buy", 10.0, 70000.0));
        });
        with_account_book("acct-iso-B", |b| {
            b.execute(&order("005930", "buy", 3.0, 70000.0));
        });
        let qa = with_account_book("acct-iso-A", |b| b.pos("005930").quantity);
        let qb = with_account_book("acct-iso-B", |b| b.pos("005930").quantity);
        assert_eq!(qa, 10.0);
        assert_eq!(qb, 3.0); // 계정별 원장 격리 — 상호 무간섭
    }

    #[test]
    fn with_book_targets_default_account() {
        with_book(|b| {
            b.execute(&order_id("035720", "buy", 7.0, 50000.0, "def-acc-coid"));
        });
        let q = with_account_book(DEFAULT_ACCOUNT, |b| b.pos("035720").quantity);
        assert_eq!(q, 7.0); // with_book == 기본 계정(하위호환)
    }

    #[test]
    fn list_accounts_includes_created() {
        with_account_book("acct-list-Z", |b| b.set_halt(false));
        assert!(list_accounts().contains(&"acct-list-Z".to_string()));
    }

    #[test]
    fn halt_is_per_account() {
        with_account_book("acct-halt-A", |b| b.set_halt(true));
        let a = with_account_book("acct-halt-A", |b| b.is_halted());
        let other = with_account_book("acct-halt-B", |b| b.is_halted());
        assert!(a);
        assert!(!other); // 계정별 독립 kill-switch
    }

    #[test]
    fn liquidate_is_per_account() {
        with_account_book("acct-liq-A", |b| {
            b.execute(&order("005930", "buy", 10.0, 70000.0));
        });
        with_account_book("acct-liq-B", |b| {
            b.execute(&order("005930", "buy", 5.0, 70000.0));
        });
        let prices = HashMap::from([("005930".to_string(), 71000.0)]);
        let n = with_account_book("acct-liq-A", |b| b.liquidate(&prices).len());
        assert_eq!(n, 1);
        // A 청산 후에도 B 보유 유지(격리).
        assert_eq!(with_account_book("acct-liq-A", |b| b.open_positions().len()), 0);
        assert_eq!(with_account_book("acct-liq-B", |b| b.pos("005930").quantity), 5.0);
    }

    #[test]
    fn buy_creates_position_with_slippage() {
        let mut b = PaperBook::new();
        let r = b.execute(&order("005930", "buy", 10.0, 70000.0));
        assert!(r.accepted);
        assert_eq!(b.pos("005930").quantity, 10.0);
        assert!(b.pos("005930").avg_price > 70000.0); // 수수료 포함 취득원가 → avg_price > 주문가
        assert_eq!(b.ledger.len(), 1);
    }

    #[test]
    fn sell_realizes_pnl() {
        let mut b = PaperBook::new();
        b.execute(&order("005930", "buy", 10.0, 70000.0));
        b.execute(&order("005930", "sell", 10.0, 77000.0));
        assert_eq!(b.pos("005930").quantity, 0.0);
        assert!(b.realized_pnl > 0.0);
        assert_eq!(b.ledger.len(), 2);
    }

    #[test]
    fn oversell_rejected() {
        let mut b = PaperBook::new();
        b.execute(&order("005930", "buy", 5.0, 70000.0));
        let r = b.execute(&order("005930", "sell", 10.0, 70000.0));
        assert!(!r.accepted);
        assert_eq!(b.pos("005930").quantity, 5.0);
    }

    #[test]
    fn zero_qty_rejected() {
        let mut b = PaperBook::new();
        let r = b.execute(&order("005930", "buy", 0.0, 70000.0));
        assert!(!r.accepted);
    }

    #[test]
    fn avg_price_on_multiple_buys() {
        let mut b = PaperBook::new();
        b.execute(&order("005930", "buy", 10.0, 70000.0));
        b.execute(&order("005930", "buy", 10.0, 72000.0));
        assert_eq!(b.pos("005930").quantity, 20.0);
        assert!(b.pos("005930").avg_price > 70900.0 && b.pos("005930").avg_price < 71100.0);
    }

    #[test]
    fn unrealized_pnl_tracks_mark() {
        let mut b = PaperBook::new();
        b.execute(&order("005930", "buy", 10.0, 70000.0));
        assert!(b.unrealized_pnl("005930", 75000.0) > 0.0);
    }

    #[test]
    fn ledger_is_append_only() {
        let mut b = PaperBook::new();
        b.execute(&order("005930", "buy", 1.0, 70000.0));
        b.execute(&order("005930", "sell", 1.0, 71000.0));
        b.execute(&order("005930", "buy", 2.0, 70500.0));
        assert_eq!(b.ledger.len(), 3);
    }

    #[test]
    fn multi_ticker_positions_isolated() {
        let mut b = PaperBook::new();
        b.execute(&order("005930", "buy", 10.0, 70000.0));
        b.execute(&order("000660", "buy", 5.0, 120000.0));
        assert_eq!(b.pos("005930").quantity, 10.0);
        assert_eq!(b.pos("000660").quantity, 5.0);
        assert_eq!(b.open_positions().len(), 2);
    }

    #[test]
    fn realized_pnl_separated_by_ticker() {
        let mut b = PaperBook::new();
        // 005930: 이익 매도
        b.execute(&order("005930", "buy", 10.0, 70000.0));
        b.execute(&order("005930", "sell", 10.0, 77000.0));
        // 000660: 손실 매도
        b.execute(&order("000660", "buy", 10.0, 120000.0));
        b.execute(&order("000660", "sell", 10.0, 110000.0));

        assert!(b.realized_for("005930") > 0.0);   // 이익
        assert!(b.realized_for("000660") < 0.0);   // 손실
        assert!(b.realized_for("미보유") == 0.0);
        // 전체 = 종목별 합
        let sum = b.realized_for("005930") + b.realized_for("000660");
        assert!((b.realized_pnl - sum).abs() < 1e-6);
    }

    #[test]
    fn mark_to_market_unrealized_by_ticker() {
        let mut b = PaperBook::new();
        b.execute(&order("005930", "buy", 10.0, 70000.0));
        b.execute(&order("000660", "buy", 5.0, 120000.0));
        let mut prices = HashMap::new();
        prices.insert("005930".to_string(), 75000.0); // 이익
        prices.insert("000660".to_string(), 115000.0); // 손실
        let un = b.unrealized_by_ticker(&prices);
        assert!(un["005930"] > 0.0);
        assert!(un["000660"] < 0.0);
    }

    #[test]
    fn mark_appends_equity_curve() {
        let mut b = PaperBook::new();
        b.execute(&order("005930", "buy", 10.0, 70000.0));
        let mut prices = HashMap::new();
        prices.insert("005930".to_string(), 72000.0);
        let p1 = b.mark(&prices, 1000);
        prices.insert("005930".to_string(), 75000.0);
        let p2 = b.mark(&prices, 2000);
        assert_eq!(b.equity_curve.len(), 2);
        assert!(p2.unrealized > p1.unrealized); // 가격 상승 → 미실현 증가
        assert!((p1.equity - (p1.realized + p1.unrealized)).abs() < 1e-6);
    }

    #[test]
    fn aggregate_daily_buckets() {
        let mut b = PaperBook::new();
        b.execute(&order("005930", "buy", 10.0, 70000.0));
        let mut prices = HashMap::new();
        // day0: ts 0, 100  | day1: ts 86400, 90000
        for (ts, px) in [(0_i64, 72000.0), (100, 75000.0), (86400, 90000.0)] {
            prices.insert("005930".to_string(), px);
            b.mark(&prices, ts);
        }
        let buckets = b.aggregate(86400);
        assert_eq!(buckets.len(), 2);          // day0, day1
        assert_eq!(buckets[0].points, 2);
        assert!(buckets[0].high >= buckets[0].open);
        assert!(buckets[1].bucket == 86400);
    }

    #[test]
    fn aggregate_empty_curve() {
        let b = PaperBook::new();
        assert!(b.aggregate(86400).is_empty());
    }

    #[test]
    fn epoch_to_ym_known_dates() {
        assert_eq!(epoch_to_ym(0), (1970, 1));           // 1970-01-01
        assert_eq!(epoch_to_ym(1_700_000_000), (2023, 11)); // 2023-11-14
        assert_eq!(epoch_to_ym(1_780_790_400), (2026, 6));  // 2026-06-07 근방
    }

    #[test]
    fn aggregate_monthly_quarterly() {
        let mut b = PaperBook::new();
        b.execute(&order("005930", "buy", 1.0, 70000.0));
        let mut prices = HashMap::new();
        // 2026-01 (Q1) x2, 2026-07 (Q3) x1
        for (ts, px) in [(1_767_225_600_i64, 71000.0), (1_767_312_000, 72000.0), (1_782_000_000, 80000.0)] {
            prices.insert("005930".to_string(), px);
            b.mark(&prices, ts);
        }
        let months = b.aggregate_calendar("month");
        assert_eq!(months.len(), 2);  // 1월, 7월
        let quarters = b.aggregate_calendar("quarter");
        assert_eq!(quarters.len(), 2); // Q1, Q3
    }

    #[test]
    fn alpha_vs_benchmark() {
        let mut b = PaperBook::new();
        b.execute(&order("005930", "buy", 10.0, 70000.0));
        let mut prices = HashMap::new();
        prices.insert("005930".to_string(), 70000.0);
        b.mark(&prices, 0);
        prices.insert("005930".to_string(), 77000.0); // +10%
        b.mark(&prices, 86400);
        // 초기자본 1,000,000, 벤치마크 +2%
        let (port, bench, alpha) = b.alpha(1_000_000.0, &[100.0, 102.0]);
        assert!(port > 0.0);
        assert!((bench - 0.02).abs() < 1e-9);
        assert!((alpha - (port - bench)).abs() < 1e-9);
    }

    #[test]
    fn alpha_insufficient_data() {
        let b = PaperBook::new();
        assert_eq!(b.alpha(1000.0, &[100.0]), (0.0, 0.0, 0.0));
    }

    #[test]
    fn risk_metrics_beta_ir_te() {
        let mut b = PaperBook::new();
        b.execute(&order("005930", "buy", 100.0, 70000.0));
        let mut prices = HashMap::new();
        // equity 4점 생성 (가격 변동)
        for (ts, px) in [(0_i64, 70000.0), (86400, 72000.0), (172800, 71000.0), (259200, 75000.0)] {
            prices.insert("005930".to_string(), px);
            b.mark(&prices, ts);
        }
        // 벤치마크 4점 (equity_curve 와 동일 길이)
        let bench = [2400.0, 2440.0, 2420.0, 2480.0];
        let (beta, ir, te) = b.risk_metrics(10_000_000.0, &bench);
        assert!(te >= 0.0);            // 트래킹에러 비음수
        assert!(beta.is_finite());
        assert!(ir.is_finite());
    }

    #[test]
    fn rolling_risk_metrics() {
        let mut b = PaperBook::new();
        b.execute(&order("005930", "buy", 100.0, 70000.0));
        let mut prices = HashMap::new();
        let pxs = [70000.0, 72000.0, 71000.0, 75000.0, 74000.0, 76000.0];
        for (i, px) in pxs.iter().enumerate() {
            prices.insert("005930".to_string(), *px);
            b.mark(&prices, i as i64 * 86400);
        }
        let bench = [2400.0, 2440.0, 2420.0, 2480.0, 2460.0, 2500.0];
        let rolling = b.risk_metrics_rolling(10_000_000.0, &bench, 4); // 윈도우 4점
        assert!(!rolling.is_empty());
        for (beta, ir, te) in &rolling {
            assert!(beta.is_finite() && ir.is_finite() && *te >= 0.0);
        }
    }

    #[test]
    fn fama_french_regression() {
        let mut b = PaperBook::new();
        b.execute(&order("005930", "buy", 100.0, 70000.0));
        let mut prices = HashMap::new();
        let pxs = [70000.0, 71000.0, 72000.0, 71500.0, 73000.0, 74000.0];
        for (i, px) in pxs.iter().enumerate() {
            prices.insert("005930".to_string(), *px);
            b.mark(&prices, i as i64 * 86400);
        }
        // 3요인 (Mkt-RF, SMB, HML), 길이 = port_returns(5)
        let mkt = vec![0.01, 0.02, -0.01, 0.015, 0.02];
        let smb = vec![0.005, -0.002, 0.003, 0.001, 0.004];
        let hml = vec![-0.001, 0.002, 0.0, 0.003, -0.002];
        let res = b.factor_regression(10_000_000.0, &[mkt, smb, hml]);
        assert!(res.is_some());
        let (alpha, betas) = res.unwrap();
        assert!(alpha.is_finite());
        assert_eq!(betas.len(), 3);
    }

    #[test]
    fn factor_regression_nw_5factor() {
        let mut b = PaperBook::new();
        b.execute(&order("005930", "buy", 100.0, 70000.0));
        let mut prices = HashMap::new();
        // 30점 → port_returns 29 (5요인+절편 6 파라미터 충분 식별)
        let pxs: Vec<f64> = (0..30).map(|i| 70000.0 + (i as f64 * 0.9).sin() * 1500.0 + i as f64 * 100.0).collect();
        for (i, px) in pxs.iter().enumerate() {
            prices.insert("005930".to_string(), *px);
            b.mark(&prices, i as i64 * 86400);
        }
        let n = pxs.len() - 1; // port_returns 길이
        // 5요인 — 서로 다른 주파수로 선형독립
        let mk = |f: f64, ph: f64| (0..n).map(|i| ((i as f64) * f + ph).sin() * 0.02).collect::<Vec<f64>>();
        let factors = vec![mk(0.3, 0.0), mk(0.7, 1.0), mk(1.1, 2.0), mk(1.7, 0.5), mk(2.3, 1.5)];
        let res = b.factor_regression_nw(10_000_000.0, &factors, 2);
        assert!(res.is_some());
        let (alpha, betas, se) = res.unwrap();
        assert!(alpha.is_finite());
        assert_eq!(betas.len(), 5);
        assert_eq!(se.len(), 6); // 절편 + 5요인
        assert!(se.iter().all(|s| s.is_finite() && *s >= 0.0));
    }

    #[test]
    fn factor_regression_nw_auto_bandwidth() {
        let mut b = PaperBook::new();
        b.execute(&order("005930", "buy", 100.0, 70000.0));
        let mut prices = HashMap::new();
        let pxs: Vec<f64> = (0..40).map(|i| 70000.0 + (i as f64 * 0.6).sin() * 1200.0 + i as f64 * 80.0).collect();
        for (i, px) in pxs.iter().enumerate() {
            prices.insert("005930".to_string(), *px);
            b.mark(&prices, i as i64 * 86400);
        }
        let n = pxs.len() - 1;
        let mk = |f: f64, ph: f64| (0..n).map(|i| ((i as f64) * f + ph).sin() * 0.02).collect::<Vec<f64>>();
        let factors = vec![mk(0.3, 0.0), mk(0.9, 1.0), mk(1.5, 2.0)];
        let res = b.factor_regression_nw_auto(10_000_000.0, &factors);
        assert!(res.is_some());
        let (alpha, betas, se, lag) = res.unwrap();
        assert!(alpha.is_finite());
        assert_eq!(betas.len(), 3);
        assert_eq!(se.len(), 4);
        // lag 은 데이터 길이 이내 자동 선택
        assert!(lag < n);
    }

    #[test]
    fn qs_kernel_hac_prewhiten() {
        let mut b = PaperBook::new();
        b.execute(&order("005930", "buy", 100.0, 70000.0));
        let mut prices = HashMap::new();
        let pxs: Vec<f64> = (0..40).map(|i| 70000.0 + (i as f64 * 0.6).sin() * 1200.0 + i as f64 * 80.0).collect();
        for (i, px) in pxs.iter().enumerate() {
            prices.insert("005930".to_string(), *px);
            b.mark(&prices, i as i64 * 86400);
        }
        let n = pxs.len() - 1;
        let mk = |f: f64, ph: f64| (0..n).map(|i| ((i as f64) * f + ph).sin() * 0.02).collect::<Vec<f64>>();
        let factors = vec![mk(0.3, 0.0), mk(0.9, 1.0), mk(1.5, 2.0)];
        // prewhiten on/off 둘 다 유한 SE
        for pw in [false, true] {
            let res = b.factor_regression_qs(10_000_000.0, &factors, 0.0, pw);
            assert!(res.is_some());
            let (alpha, betas, se) = res.unwrap();
            assert!(alpha.is_finite());
            assert_eq!(betas.len(), 3);
            assert_eq!(se.len(), 4);
            assert!(se.iter().all(|s| s.is_finite() && *s >= 0.0));
        }
    }

    #[test]
    fn qs_full_var_prewhiten() {
        let mut b = PaperBook::new();
        b.execute(&order("005930", "buy", 100.0, 70000.0));
        let mut prices = HashMap::new();
        let pxs: Vec<f64> = (0..40).map(|i| 70000.0 + (i as f64 * 0.6).sin() * 1200.0 + i as f64 * 80.0).collect();
        for (i, px) in pxs.iter().enumerate() {
            prices.insert("005930".to_string(), *px);
            b.mark(&prices, i as i64 * 86400);
        }
        let n = pxs.len() - 1;
        let mk = |f: f64, ph: f64| (0..n).map(|i| ((i as f64) * f + ph).sin() * 0.02).collect::<Vec<f64>>();
        let factors = vec![mk(0.3, 0.0), mk(0.9, 1.0), mk(1.5, 2.0)];
        // full VAR(1) prewhitening
        let res = b.factor_regression_qs_full(10_000_000.0, &factors, 0.0, true, true);
        assert!(res.is_some());
        let (alpha, betas, se) = res.unwrap();
        assert!(alpha.is_finite());
        assert_eq!(betas.len(), 3);
        assert_eq!(se.len(), 4);
        assert!(se.iter().all(|s| s.is_finite() && *s >= 0.0));
    }

    #[test]
    fn qs_aic_order_selection() {
        let mut b = PaperBook::new();
        b.execute(&order("005930", "buy", 100.0, 70000.0));
        let mut prices = HashMap::new();
        let pxs: Vec<f64> = (0..50).map(|i| 70000.0 + (i as f64 * 0.6).sin() * 1200.0 + i as f64 * 80.0).collect();
        for (i, px) in pxs.iter().enumerate() {
            prices.insert("005930".to_string(), *px);
            b.mark(&prices, i as i64 * 86400);
        }
        let n = pxs.len() - 1;
        let mk = |f: f64, ph: f64| (0..n).map(|i| ((i as f64) * f + ph).sin() * 0.02).collect::<Vec<f64>>();
        let factors = vec![mk(0.3, 0.0), mk(0.9, 1.0), mk(1.5, 2.0)];
        let res = b.factor_regression_qs_aic(10_000_000.0, &factors, 5);
        assert!(res.is_some());
        let (alpha, betas, se, p) = res.unwrap();
        assert!(alpha.is_finite());
        assert_eq!(betas.len(), 3);
        assert_eq!(se.len(), 4);
        assert!(p <= 5);  // 선택 차수 범위 내
        assert!(se.iter().all(|s| s.is_finite() && *s >= 0.0));
    }

    #[test]
    fn qs_var_p_bic_hq() {
        let mut b = PaperBook::new();
        b.execute(&order("005930", "buy", 100.0, 70000.0));
        let mut prices = HashMap::new();
        let pxs: Vec<f64> = (0..60).map(|i| 70000.0 + (i as f64 * 0.5).sin() * 1200.0 + i as f64 * 70.0).collect();
        for (i, px) in pxs.iter().enumerate() {
            prices.insert("005930".to_string(), *px);
            b.mark(&prices, i as i64 * 86400);
        }
        let n = pxs.len() - 1;
        let mk = |f: f64, ph: f64| (0..n).map(|i| ((i as f64) * f + ph).sin() * 0.02).collect::<Vec<f64>>();
        let factors = vec![mk(0.3, 0.0), mk(0.9, 1.0)];
        for crit in ["aic", "bic", "hq"] {
            let res = b.factor_regression_qs_var(10_000_000.0, &factors, 3, crit);
            assert!(res.is_some(), "{crit}");
            let (alpha, betas, se, p) = res.unwrap();
            assert!(alpha.is_finite());
            assert_eq!(betas.len(), 2);
            assert_eq!(se.len(), 3);
            assert!(p <= 3);
            assert!(se.iter().all(|s| s.is_finite() && *s >= 0.0));
        }
    }

    #[test]
    fn qs_var_stabilize() {
        let mut b = PaperBook::new();
        b.execute(&order("005930", "buy", 100.0, 70000.0));
        let mut prices = HashMap::new();
        let pxs: Vec<f64> = (0..60).map(|i| 70000.0 + (i as f64 * 0.5).sin() * 1200.0 + i as f64 * 70.0).collect();
        for (i, px) in pxs.iter().enumerate() {
            prices.insert("005930".to_string(), *px);
            b.mark(&prices, i as i64 * 86400);
        }
        let n = pxs.len() - 1;
        let mk = |f: f64, ph: f64| (0..n).map(|i| ((i as f64) * f + ph).sin() * 0.02).collect::<Vec<f64>>();
        let factors = vec![mk(0.3, 0.0), mk(0.9, 1.0)];
        let res = b.factor_regression_qs_var_opt(10_000_000.0, &factors, 3, "bic", true);
        assert!(res.is_some());
        let (alpha, betas, se, _p) = res.unwrap();
        assert!(alpha.is_finite());
        assert_eq!(betas.len(), 2);
        assert!(se.iter().all(|s| s.is_finite() && *s >= 0.0));
    }

    #[test]
    fn qs_var_companion_stabilize() {
        let mut b = PaperBook::new();
        b.execute(&order("005930", "buy", 100.0, 70000.0));
        let mut prices = HashMap::new();
        let pxs: Vec<f64> = (0..60).map(|i| 70000.0 + (i as f64 * 0.5).sin() * 1200.0 + i as f64 * 70.0).collect();
        for (i, px) in pxs.iter().enumerate() {
            prices.insert("005930".to_string(), *px);
            b.mark(&prices, i as i64 * 86400);
        }
        let n = pxs.len() - 1;
        let mk = |f: f64, ph: f64| (0..n).map(|i| ((i as f64) * f + ph).sin() * 0.02).collect::<Vec<f64>>();
        let factors = vec![mk(0.3, 0.0), mk(0.9, 1.0)];
        // companion 기반 안정성 사영
        let res = b.factor_regression_qs_var_full(10_000_000.0, &factors, 3, "aic", true, true);
        assert!(res.is_some());
        let (alpha, betas, se, _p) = res.unwrap();
        assert!(alpha.is_finite());
        assert_eq!(betas.len(), 2);
        assert!(se.iter().all(|s| s.is_finite() && *s >= 0.0));
    }

    #[test]
    fn companion_matrix_radius() {
        // VAR(2) cols=1: A_1=0.5, A_2=0.3 → companion [[0.5,0.3],[1,0]], 반경<1
        let a_list = vec![vec![vec![0.5]], vec![vec![0.3]]];
        let c = build_companion(&a_list, 1, 2);
        assert_eq!(c.len(), 2);
        assert!((c[1][0] - 1.0).abs() < 1e-9);  // 시프트 항등
        let r = companion_radius(&a_list, 1, 2);
        assert!(r < 1.0 && r > 0.0);  // 정상(안정) VAR
    }

    #[test]
    fn qr_eigenvalues_real_and_complex() {
        // 대각 행렬 → 고유값 = 대각 (실수)
        let d = vec![vec![3.0, 0.0], vec![0.0, -2.0]];
        let mut m = qr_eigen_magnitudes(&d);
        m.sort_by(|a, b| b.partial_cmp(a).unwrap());
        assert!((m[0] - 3.0).abs() < 1e-3 && (m[1] - 2.0).abs() < 1e-3);
        // 회전행렬 [[0,-1],[1,0]] → 복소 고유값 ±i, |λ|=1
        let rot = vec![vec![0.0, -1.0], vec![1.0, 0.0]];
        let mr = qr_eigen_magnitudes(&rot);
        assert!(mr.iter().all(|x| (x - 1.0).abs() < 1e-3));
    }

    #[test]
    fn companion_radius_qr_complex() {
        // 진동형 VAR(2): A1=0.0, A2=-0.5 → companion 복소 고유값
        let a_list = vec![vec![vec![0.0]], vec![vec![-0.5]]];
        let r = companion_radius_qr(&a_list, 1, 2);
        // |λ| = sqrt(0.5) ≈ 0.707
        assert!((r - 0.5_f64.sqrt()).abs() < 0.05);
    }

    #[test]
    fn spectral_radius_and_stabilize() {
        let a = vec![vec![0.5, 0.0], vec![0.0, 0.3]];  // 대각 → 반경 0.5
        assert!((spectral_radius(&a, 100) - 0.5).abs() < 1e-3);
        // 불안정(반경 2) → 스케일 < 1
        let big = vec![vec![2.0, 0.0], vec![0.0, 1.5]];
        let sc = stabilize_scale(&big, 0.97);
        assert!(sc < 1.0);
        assert!(spectral_radius(&big, 100) * sc <= 0.971);
    }

    #[test]
    fn yule_walker_ar1() {
        // 강한 AR(1) ρ=0.8 + LCG 백색노이즈 → φ₁ ≈ 0.8
        let mut seed: u64 = 12345;
        let mut rand = || {
            seed = seed.wrapping_mul(6364136223846793005).wrapping_add(1442695040888963407);
            ((seed >> 33) as f64) / (1u64 << 31) as f64 - 1.0
        };
        let mut s = vec![0.0f64; 500];
        for t in 1..500 {
            s[t] = 0.8 * s[t - 1] + rand() * 0.3;
        }
        let phi = ar_yule_walker(&s, 1).unwrap();
        assert!(phi[0] > 0.6 && phi[0] < 0.95);  // 강한 양의 지속성 탐지
    }

    #[test]
    fn det_and_var_order() {
        // det 단위행렬=1, 대각=곱
        let i3 = vec![vec![1.0, 0.0, 0.0], vec![0.0, 1.0, 0.0], vec![0.0, 0.0, 1.0]];
        assert!((det(&i3) - 1.0).abs() < 1e-9);
        let d = vec![vec![2.0, 0.0], vec![0.0, 3.0]];
        assert!((det(&d) - 6.0).abs() < 1e-9);
    }

    #[test]
    fn aic_ar_order_picks_persistent() {
        // 강한 AR(1) 계열 → 차수 ≥1 선택
        let mut s = vec![0.0f64; 100];
        for t in 1..100 {
            s[t] = 0.8 * s[t - 1] + ((t * 13 % 7) as f64 - 3.0) * 0.1;
        }
        let p = aic_ar_order(&s, 5);
        assert!(p >= 1);
        // 백색잡음 유사 → 작은 차수
        let noise: Vec<f64> = (0..100).map(|i| ((i * 37 % 101) as f64 - 50.0) * 0.01).collect();
        assert!(aic_ar_order(&noise, 5) <= 5);
    }

    #[test]
    fn qs_weight_properties() {
        assert!((qs_weight(0.0) - 1.0).abs() < 1e-9); // x=0 → 1
        assert!(qs_weight(1.0).abs() <= 1.0);          // 감쇠
        assert!(qs_weight(5.0).abs() < 0.1);           // 먼 시차 → 작음
    }

    #[test]
    fn andrews_bandwidth_basics() {
        // 무상관 잡음 → 작은 lag
        let noise: Vec<f64> = (0..50).map(|i| ((i * 7 % 11) as f64 - 5.0) * 0.01).collect();
        let lag = andrews_bandwidth(&noise);
        assert!(lag < 50);
        // 짧은 시계열 → 0
        assert_eq!(andrews_bandwidth(&[0.1, 0.2]), 0);
    }

    #[test]
    fn factor_regression_nw_lag0_matches_plain() {
        let mut b = PaperBook::new();
        b.execute(&order("005930", "buy", 100.0, 70000.0));
        let mut prices = HashMap::new();
        let pxs = [70000.0, 71000.0, 72000.0, 71500.0, 73000.0, 74000.0];
        for (i, px) in pxs.iter().enumerate() {
            prices.insert("005930".to_string(), *px);
            b.mark(&prices, i as i64 * 86400);
        }
        let n = pxs.len() - 1;
        let f1: Vec<f64> = (0..n).map(|i| (i as f64) * 0.01).collect();
        let plain = b.factor_regression(10_000_000.0, &[f1.clone()]).unwrap();
        let (alpha, betas, _se) = b.factor_regression_nw(10_000_000.0, &[f1], 0).unwrap();
        // 계수는 NW 와 무관하게 동일
        assert!((alpha - plain.0).abs() < 1e-6);
        assert!((betas[0] - plain.1[0]).abs() < 1e-6);
    }

    #[test]
    fn factor_regression_length_mismatch() {
        let mut b = PaperBook::new();
        b.execute(&order("005930", "buy", 1.0, 70000.0));
        let mut prices = HashMap::new();
        for i in 0..5 {
            prices.insert("005930".to_string(), 70000.0 + i as f64 * 100.0);
            b.mark(&prices, i as i64);
        }
        // 잘못된 길이 → None
        assert!(b.factor_regression(1_000_000.0, &[vec![0.1, 0.2]]).is_none());
    }

    #[test]
    fn risk_metrics_length_mismatch() {
        let mut b = PaperBook::new();
        b.execute(&order("005930", "buy", 1.0, 70000.0));
        let mut prices = HashMap::new();
        prices.insert("005930".to_string(), 71000.0);
        b.mark(&prices, 0);
        b.mark(&prices, 1);
        b.mark(&prices, 2);
        // 벤치 길이 불일치 → 0
        assert_eq!(b.risk_metrics(1_000_000.0, &[100.0, 101.0]), (0.0, 0.0, 0.0));
    }

    #[test]
    fn mark_ignores_unpriced_and_flat() {
        let mut b = PaperBook::new();
        b.execute(&order("005930", "buy", 10.0, 70000.0));
        let prices = HashMap::new(); // 가격 없음
        let un = b.unrealized_by_ticker(&prices);
        assert!(un.is_empty());
    }

    #[test]
    fn replay_rebuilds_positions() {
        let mut b = PaperBook::new();
        b.execute(&order("005930", "buy", 10.0, 70000.0));
        b.execute(&order("000660", "buy", 5.0, 120000.0));
        let fills = b.ledger.clone();

        let mut restored = PaperBook::new();
        restored.replay(&fills);
        assert_eq!(restored.pos("005930").quantity, 10.0);
        assert_eq!(restored.pos("000660").quantity, 5.0);
    }
}
