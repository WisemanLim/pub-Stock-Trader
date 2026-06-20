//! F4 리스크 규칙 엔진 — 감정 배제 기계적 판정 (순수 함수, 무상태).
//! Stop-Loss · Trailing Stop · Take-Profit · 일일 최대손실 · 포지션 사이징 · Fail-Safe.

use serde::{Deserialize, Serialize};

/// 리스크 판정 입력 — 포지션 상태 + 페르소나별 규칙 파라미터.
#[derive(Debug, Clone, Deserialize)]
pub struct RiskRequest {
    pub ticker: String,
    pub entry_price: f64,
    pub current_price: f64,
    /// 보유 후 갱신된 최고가 (Trailing Stop 기준). 없으면 entry_price 사용.
    #[serde(default)]
    pub highest_price: f64,
    /// 현재 단일 종목 비중 (0.0~1.0).
    #[serde(default)]
    pub position_pct: f64,
    /// 당일 누적 손익률 (예: -0.04 = -4%).
    #[serde(default)]
    pub account_pnl_pct: f64,

    // ── 규칙 파라미터 (페르소나별 설정) ──
    pub stop_loss_pct: f64,       // 예: 0.02 = -2%
    #[serde(default)]
    pub trailing_pct: f64,        // 0 이면 비활성
    #[serde(default)]
    pub take_profit_pct: f64,     // 0 이면 비활성
    pub daily_loss_limit_pct: f64, // 예: 0.05 = -5%
    pub max_position_pct: f64,    // 예: 0.10 = 10%

    /// 브로커 세션 연결 상태. false → Fail-Safe.
    #[serde(default = "default_true")]
    pub broker_connected: bool,

    // ── Phase B 추가 필드 ──
    /// KRX 시장경보 레벨. 0=정상, 1=투자주의, 2=투자경고, 3=투자위험/정리매매.
    #[serde(default)]
    pub market_alert_level: u8,
    /// 공매도 비율 (0.0~1.0). 0 이면 비활성.
    #[serde(default)]
    pub short_ratio: f64,
    /// 공매도 비율 임계치. 0 이면 규칙 비활성.
    #[serde(default)]
    pub short_ratio_limit: f64,
}

fn default_true() -> bool {
    true
}

/// 최종 조치. 우선순위: ForceSell > BlockBuy > ReducePosition > Hold.
#[derive(Debug, Clone, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum Action {
    /// 즉시 시장가 전량 매도 (Stop-Loss / Trailing / 일일한도 청산).
    ForceSell,
    /// 익절 분할 매도.
    TakeProfit,
    /// 신규 매수 차단 (Fail-Safe / 일일한도).
    BlockBuy,
    /// 비중 초과 → 축소.
    ReducePosition,
    /// 조치 없음.
    Hold,
}

#[derive(Debug, Clone, Serialize)]
pub struct RiskDecision {
    pub ticker: String,
    pub action: Action,
    /// 발동된 규칙 식별자 목록 (감사 로그용).
    pub triggered: Vec<String>,
    pub reason: String,
}

/// 리스크 판정 — 모든 규칙 평가 후 최고 우선순위 조치 반환.
pub fn evaluate(req: &RiskRequest) -> RiskDecision {
    let mut triggered: Vec<String> = Vec::new();
    let mut reasons: Vec<String> = Vec::new();

    let highest = if req.highest_price > 0.0 {
        req.highest_price
    } else {
        req.entry_price
    };

    // 1) Fail-Safe — 브로커 세션 유실 → 신규 진입 차단 (NFR).
    if !req.broker_connected {
        triggered.push("fail_safe".into());
        reasons.push("브로커 세션 유실 — 신규 매수 전면 차단".into());
    }

    // 2) Stop-Loss — 매수단가 대비 손절선 도달 → 즉시 매도.
    let stop_line = req.entry_price * (1.0 - req.stop_loss_pct);
    if req.current_price <= stop_line {
        triggered.push("stop_loss".into());
        reasons.push(format!(
            "Stop-Loss: {:.2} <= {:.2} (-{:.1}%)",
            req.current_price, stop_line, req.stop_loss_pct * 100.0
        ));
    }

    // 3) Trailing Stop — 최고가 대비 하락폭 도달 → 즉시 매도.
    if req.trailing_pct > 0.0 {
        let trail_line = highest * (1.0 - req.trailing_pct);
        if req.current_price <= trail_line && highest > req.entry_price {
            triggered.push("trailing_stop".into());
            reasons.push(format!(
                "Trailing Stop: {:.2} <= {:.2} (최고가 {:.2} 대비 -{:.1}%)",
                req.current_price, trail_line, highest, req.trailing_pct * 100.0
            ));
        }
    }

    // 4) 일일 최대손실 한도 — 초과 시 신규 매수 차단 + 단계 청산.
    if req.account_pnl_pct <= -req.daily_loss_limit_pct {
        triggered.push("daily_loss_limit".into());
        reasons.push(format!(
            "일일 손실 한도: {:.1}% <= -{:.1}%",
            req.account_pnl_pct * 100.0, req.daily_loss_limit_pct * 100.0
        ));
    }

    // 5) Take-Profit — 목표 수익 도달 → 분할/전량 익절.
    if req.take_profit_pct > 0.0 {
        let tp_line = req.entry_price * (1.0 + req.take_profit_pct);
        if req.current_price >= tp_line {
            triggered.push("take_profit".into());
            reasons.push(format!(
                "Take-Profit: {:.2} >= {:.2} (+{:.1}%)",
                req.current_price, tp_line, req.take_profit_pct * 100.0
            ));
        }
    }

    // 6) 포지션 사이징 — 단일 종목 한도 초과 → 축소.
    if req.position_pct > req.max_position_pct {
        triggered.push("position_sizing".into());
        reasons.push(format!(
            "포지션 한도 초과: {:.1}% > {:.1}%",
            req.position_pct * 100.0, req.max_position_pct * 100.0
        ));
    }

    // 7) Phase B-2: KRX 시장경보 — 위험/정리매매(3) → 긴급청산, 경고(2) → 신규매수 차단.
    if req.market_alert_level >= 3 {
        triggered.push("market_alert_danger".into());
        reasons.push(format!(
            "시장경보 위험(레벨 {}) — 긴급청산 트리거",
            req.market_alert_level
        ));
    } else if req.market_alert_level == 2 {
        triggered.push("market_alert_warning".into());
        reasons.push("시장경보 경고(레벨 2) — 신규 매수 차단".into());
    }

    // 8) Phase B-4: 공매도 과열 — 비율 임계치 초과 시 포지션 축소.
    if req.short_ratio_limit > 0.0 && req.short_ratio > req.short_ratio_limit {
        triggered.push("short_sell_excess".into());
        reasons.push(format!(
            "공매도 과열: {:.1}% > {:.1}% 임계치 — 포지션 축소",
            req.short_ratio * 100.0, req.short_ratio_limit * 100.0
        ));
    }

    // ── 우선순위 결정 ──
    let has = |k: &str| triggered.iter().any(|t| t == k);
    let action = if has("stop_loss") || has("trailing_stop") || has("daily_loss_limit") || has("market_alert_danger") {
        Action::ForceSell
    } else if has("take_profit") {
        Action::TakeProfit
    } else if has("fail_safe") || has("market_alert_warning") {
        Action::BlockBuy
    } else if has("position_sizing") || has("short_sell_excess") {
        Action::ReducePosition
    } else {
        Action::Hold
    };

    let reason = if reasons.is_empty() {
        "모든 리스크 규칙 통과".into()
    } else {
        reasons.join(" | ")
    };

    RiskDecision {
        ticker: req.ticker.clone(),
        action,
        triggered,
        reason,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn base() -> RiskRequest {
        RiskRequest {
            ticker: "005930".into(),
            entry_price: 70000.0,
            current_price: 70000.0,
            highest_price: 0.0,
            position_pct: 0.05,
            account_pnl_pct: 0.0,
            stop_loss_pct: 0.02,
            trailing_pct: 0.0,
            take_profit_pct: 0.0,
            daily_loss_limit_pct: 0.05,
            max_position_pct: 0.10,
            broker_connected: true,
            market_alert_level: 0,
            short_ratio: 0.0,
            short_ratio_limit: 0.0,
        }
    }

    #[test]
    fn hold_when_all_pass() {
        let d = evaluate(&base());
        assert_eq!(d.action, Action::Hold);
        assert!(d.triggered.is_empty());
    }

    #[test]
    fn stop_loss_triggers_force_sell() {
        let mut r = base();
        r.current_price = 68600.0; // -2% 정확히
        let d = evaluate(&r);
        assert_eq!(d.action, Action::ForceSell);
        assert!(d.triggered.contains(&"stop_loss".to_string()));
    }

    #[test]
    fn stop_loss_not_triggered_above_line() {
        let mut r = base();
        r.current_price = 69000.0; // -1.4%, 손절선 위
        let d = evaluate(&r);
        assert_eq!(d.action, Action::Hold);
    }

    #[test]
    fn trailing_stop_protects_profit() {
        let mut r = base();
        r.current_price = 75000.0;
        r.highest_price = 80000.0;
        r.trailing_pct = 0.05; // 최고가 -5% = 76000
        let d = evaluate(&r);
        assert_eq!(d.action, Action::ForceSell);
        assert!(d.triggered.contains(&"trailing_stop".to_string()));
    }

    #[test]
    fn trailing_ignored_when_below_entry() {
        let mut r = base();
        r.current_price = 69000.0;
        r.highest_price = 69500.0; // 진입가 미만 → 트레일링 무시
        r.trailing_pct = 0.01;
        let d = evaluate(&r);
        assert!(!d.triggered.contains(&"trailing_stop".to_string()));
    }

    #[test]
    fn take_profit_triggers() {
        let mut r = base();
        r.current_price = 77000.0;
        r.take_profit_pct = 0.10; // +10% = 77000
        let d = evaluate(&r);
        assert_eq!(d.action, Action::TakeProfit);
    }

    #[test]
    fn daily_loss_limit_blocks() {
        let mut r = base();
        r.account_pnl_pct = -0.05;
        let d = evaluate(&r);
        assert_eq!(d.action, Action::ForceSell);
        assert!(d.triggered.contains(&"daily_loss_limit".to_string()));
    }

    #[test]
    fn fail_safe_blocks_buy() {
        let mut r = base();
        r.broker_connected = false;
        let d = evaluate(&r);
        assert_eq!(d.action, Action::BlockBuy);
        assert!(d.triggered.contains(&"fail_safe".to_string()));
    }

    #[test]
    fn position_sizing_reduces() {
        let mut r = base();
        r.position_pct = 0.15; // 한도 10% 초과
        let d = evaluate(&r);
        assert_eq!(d.action, Action::ReducePosition);
    }

    #[test]
    fn stop_loss_priority_over_position_sizing() {
        let mut r = base();
        r.current_price = 68000.0; // stop-loss 발동
        r.position_pct = 0.15;     // 사이징도 발동
        let d = evaluate(&r);
        assert_eq!(d.action, Action::ForceSell); // 청산이 우선
        assert_eq!(d.triggered.len(), 2);
    }

    // Phase B-2: 시장경보 규칙
    #[test]
    fn market_alert_danger_force_sell() {
        let mut r = base();
        r.market_alert_level = 3;
        let d = evaluate(&r);
        assert_eq!(d.action, Action::ForceSell);
        assert!(d.triggered.contains(&"market_alert_danger".to_string()));
    }

    #[test]
    fn market_alert_level4_also_danger() {
        let mut r = base();
        r.market_alert_level = 4; // 정리매매
        let d = evaluate(&r);
        assert_eq!(d.action, Action::ForceSell);
    }

    #[test]
    fn market_alert_warning_blocks_buy() {
        let mut r = base();
        r.market_alert_level = 2;
        let d = evaluate(&r);
        assert_eq!(d.action, Action::BlockBuy);
        assert!(d.triggered.contains(&"market_alert_warning".to_string()));
    }

    #[test]
    fn market_alert_caution_no_action() {
        let mut r = base();
        r.market_alert_level = 1; // 투자주의는 규칙 미발동
        let d = evaluate(&r);
        assert_eq!(d.action, Action::Hold);
    }

    #[test]
    fn market_alert_zero_normal() {
        let r = base(); // market_alert_level = 0 (default)
        let d = evaluate(&r);
        assert_eq!(d.action, Action::Hold);
    }

    // Phase B-4: 공매도 과열 규칙
    #[test]
    fn short_sell_excess_reduces_position() {
        let mut r = base();
        r.short_ratio = 0.25;
        r.short_ratio_limit = 0.20;
        let d = evaluate(&r);
        assert_eq!(d.action, Action::ReducePosition);
        assert!(d.triggered.contains(&"short_sell_excess".to_string()));
    }

    #[test]
    fn short_sell_below_limit_no_action() {
        let mut r = base();
        r.short_ratio = 0.10;
        r.short_ratio_limit = 0.20;
        let d = evaluate(&r);
        assert_eq!(d.action, Action::Hold);
    }

    #[test]
    fn short_sell_limit_zero_disabled() {
        let mut r = base();
        r.short_ratio = 0.99; // 한도 0 → 규칙 비활성
        r.short_ratio_limit = 0.0;
        let d = evaluate(&r);
        assert_eq!(d.action, Action::Hold);
    }

    #[test]
    fn market_alert_danger_overrides_short_sell() {
        let mut r = base();
        r.market_alert_level = 3;
        r.short_ratio = 0.99;
        r.short_ratio_limit = 0.10;
        let d = evaluate(&r);
        assert_eq!(d.action, Action::ForceSell); // 위험이 우선
    }
}
