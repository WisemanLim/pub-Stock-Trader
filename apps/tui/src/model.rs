//! F6.1 TUI 상태 모델 — 순수 로직 (렌더/IO 분리, 테스트 가능).

/// 호가 한 레벨.
#[derive(Debug, Clone)]
pub struct Level {
    pub price: f64,
    pub qty: u64,
}

/// Phase B: KRX 시장경보 항목.
#[derive(Debug, Clone)]
pub struct AlertItem {
    pub ticker: String,
    pub level: u8, // 1=주의 2=경고 3=위험
    pub name: String,
}

impl AlertItem {
    pub fn label(&self) -> &'static str {
        match self.level {
            1 => "주의",
            2 => "경고",
            _ => "위험",
        }
    }
}

/// 포지션 + 호가창 + P&L + 시장경보 스캘퍼 콘솔 상태.
#[derive(Debug, Clone)]
pub struct AppState {
    pub ticker: String,
    pub asks: Vec<Level>, // 오름차순 (best ask = asks[0])
    pub bids: Vec<Level>, // 내림차순 (best bid = bids[0])
    pub entry_price: f64,
    pub position_qty: u64,
    pub last_price: f64,
    pub should_quit: bool,
    pub status: String,
    /// Phase B-5: 활성 시장경보 목록.
    pub alerts: Vec<AlertItem>,
    /// Phase B-5: 현재 종목 공매도 비율 (0.0~1.0).
    pub short_ratio: f64,
}

impl AppState {
    pub fn new(ticker: &str) -> Self {
        Self {
            ticker: ticker.to_string(),
            asks: Vec::new(),
            bids: Vec::new(),
            entry_price: 0.0,
            position_qty: 0,
            last_price: 0.0,
            should_quit: false,
            status: "대기".into(),
            alerts: Vec::new(),
            short_ratio: 0.0,
        }
    }

    /// 최우선 매수/매도 호가 스프레드. 데이터 없으면 None.
    pub fn spread(&self) -> Option<f64> {
        match (self.bids.first(), self.asks.first()) {
            (Some(b), Some(a)) => Some(a.price - b.price),
            _ => None,
        }
    }

    /// 중간가.
    pub fn mid_price(&self) -> Option<f64> {
        match (self.bids.first(), self.asks.first()) {
            (Some(b), Some(a)) => Some((a.price + b.price) / 2.0),
            _ => None,
        }
    }

    /// 미실현 손익 (현재가 - 진입가) * 수량. 포지션 없으면 0.
    pub fn unrealized_pnl(&self) -> f64 {
        if self.position_qty == 0 || self.entry_price == 0.0 {
            return 0.0;
        }
        (self.last_price - self.entry_price) * self.position_qty as f64
    }

    /// 손익률 (%).
    pub fn pnl_pct(&self) -> f64 {
        if self.entry_price == 0.0 {
            return 0.0;
        }
        (self.last_price - self.entry_price) / self.entry_price * 100.0
    }

    /// 핫키 처리. 반환: 처리됨 여부.
    pub fn handle_key(&mut self, key: char) -> bool {
        match key {
            'q' | 'Q' => {
                self.should_quit = true;
                self.status = "종료".into();
                true
            }
            'b' | 'B' => {
                // 시장가 매수 (best ask 체결 가정)
                if let Some(a) = self.asks.first() {
                    let price = a.price;
                    let new_qty = self.position_qty + 1;
                    // 평균 단가 갱신
                    self.entry_price = (self.entry_price * self.position_qty as f64
                        + price)
                        / new_qty as f64;
                    self.position_qty = new_qty;
                    self.last_price = price;
                    self.status = format!("매수 1주 @ {:.0}", price);
                }
                true
            }
            's' | 'S' => {
                // 시장가 매도 (best bid 체결)
                if self.position_qty > 0 {
                    if let Some(b) = self.bids.first() {
                        self.position_qty -= 1;
                        self.last_price = b.price;
                        if self.position_qty == 0 {
                            self.entry_price = 0.0;
                        }
                        self.status = format!("매도 1주 @ {:.0}", b.price);
                    }
                }
                true
            }
            _ => false,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn seeded() -> AppState {
        let mut s = AppState::new("005930");
        s.asks = vec![
            Level { price: 70100.0, qty: 100 },
            Level { price: 70200.0, qty: 200 },
        ];
        s.bids = vec![
            Level { price: 70000.0, qty: 150 },
            Level { price: 69900.0, qty: 250 },
        ];
        s
    }

    #[test]
    fn spread_and_mid() {
        let s = seeded();
        assert_eq!(s.spread(), Some(100.0));
        assert_eq!(s.mid_price(), Some(70050.0));
    }

    #[test]
    fn spread_none_without_data() {
        let s = AppState::new("005930");
        assert_eq!(s.spread(), None);
        assert_eq!(s.mid_price(), None);
    }

    #[test]
    fn buy_sets_position() {
        let mut s = seeded();
        assert!(s.handle_key('b'));
        assert_eq!(s.position_qty, 1);
        assert_eq!(s.entry_price, 70100.0); // best ask
    }

    #[test]
    fn buy_twice_averages_entry() {
        let mut s = seeded();
        s.handle_key('b'); // @70100
        s.asks[0].price = 70300.0;
        s.handle_key('b'); // @70300
        assert_eq!(s.position_qty, 2);
        assert_eq!(s.entry_price, 70200.0); // 평균
    }

    #[test]
    fn sell_reduces_position() {
        let mut s = seeded();
        s.handle_key('b');
        s.handle_key('s');
        assert_eq!(s.position_qty, 0);
        assert_eq!(s.entry_price, 0.0); // 전량 청산 시 리셋
    }

    #[test]
    fn sell_without_position_noop() {
        let mut s = seeded();
        s.handle_key('s');
        assert_eq!(s.position_qty, 0);
    }

    #[test]
    fn unrealized_pnl_calc() {
        let mut s = seeded();
        s.handle_key('b'); // entry 70100, qty 1
        s.last_price = 70600.0;
        assert_eq!(s.unrealized_pnl(), 500.0);
        assert!((s.pnl_pct() - 0.712).abs() < 0.01);
    }

    #[test]
    fn quit_sets_flag() {
        let mut s = seeded();
        assert!(s.handle_key('q'));
        assert!(s.should_quit);
    }

    #[test]
    fn unknown_key_ignored() {
        let mut s = seeded();
        assert!(!s.handle_key('x'));
    }
}
