// stock-trader tui — ratatui 기반 스캘퍼 콘솔 (F6.1 + Phase B-5)
// 키보드 핫키 중심: [b]매수 [s]매도 [q]종료. 호가창·포지션·P&L·시장경보 실시간 표시.
mod model;

use std::io;
use std::time::Duration;

use crossterm::event::{self, Event, KeyCode};
use crossterm::terminal::{disable_raw_mode, enable_raw_mode, EnterAlternateScreen, LeaveAlternateScreen};
use crossterm::execute;
use ratatui::prelude::*;
use ratatui::widgets::{Block, Borders, Cell, Paragraph, Row, Table};

use model::{AlertItem, AppState, Level};

fn main() -> io::Result<()> {
    enable_raw_mode()?;
    let mut stdout = io::stdout();
    execute!(stdout, EnterAlternateScreen)?;
    let backend = CrosstermBackend::new(stdout);
    let mut terminal = Terminal::new(backend)?;

    let mut state = demo_state();
    let res = run(&mut terminal, &mut state);

    disable_raw_mode()?;
    execute!(terminal.backend_mut(), LeaveAlternateScreen)?;
    terminal.show_cursor()?;
    res
}

/// 데모 호가 시드 (브로커 WS 미연결 시). 실연동: ingest :8003 WebSocket.
fn demo_state() -> AppState {
    let mut s = AppState::new("005930");
    s.asks = vec![
        Level { price: 70300.0, qty: 120 },
        Level { price: 70200.0, qty: 340 },
        Level { price: 70100.0, qty: 510 },
    ];
    s.bids = vec![
        Level { price: 70000.0, qty: 230 },
        Level { price: 69900.0, qty: 410 },
        Level { price: 69800.0, qty: 150 },
    ];
    s.last_price = 70050.0;
    // Phase B-5 데모: 시장경보 + 공매도 비율
    s.alerts = vec![
        AlertItem { ticker: "000660".into(), level: 2, name: "SK하이닉스".into() },
        AlertItem { ticker: "010130".into(), level: 1, name: "고려아연".into() },
    ];
    s.short_ratio = 0.087; // 8.7%
    s
}

fn run<B: Backend>(terminal: &mut Terminal<B>, state: &mut AppState) -> io::Result<()> {
    loop {
        terminal.draw(|f| ui(f, state))?;
        if event::poll(Duration::from_millis(200))? {
            if let Event::Key(key) = event::read()? {
                if let KeyCode::Char(c) = key.code {
                    state.handle_key(c);
                }
            }
        }
        if state.should_quit {
            return Ok(());
        }
    }
}

fn ui(f: &mut Frame, state: &AppState) {
    let chunks = Layout::default()
        .direction(Direction::Vertical)
        .constraints([
            Constraint::Length(3), // 헤더
            Constraint::Length(3), // Phase B-5: 시장경보 배너
            Constraint::Min(8),    // 호가창
            Constraint::Length(5), // 포지션/P&L
        ])
        .split(f.area());

    // 헤더
    let header = Paragraph::new(format!(
        " {} │ 중간가 {:.0} │ 스프레드 {:.0} │ 공매도 {:.1}%",
        state.ticker,
        state.mid_price().unwrap_or(0.0),
        state.spread().unwrap_or(0.0),
        state.short_ratio * 100.0,
    ))
    .block(Block::default().borders(Borders::ALL).title("stock-trader 스캘퍼 콘솔 (Phase B)"));
    f.render_widget(header, chunks[0]);

    // Phase B-5: 시장경보 배너
    let (alert_text, alert_style) = if state.alerts.is_empty() {
        (
            " ✓ 시장경보 없음".to_string(),
            Style::default().fg(Color::Green),
        )
    } else {
        let parts: Vec<String> = state.alerts.iter().map(|a| {
            format!("[{}] {} {}", a.label(), a.ticker, a.name)
        }).collect();
        let color = if state.alerts.iter().any(|a| a.level >= 3) {
            Color::Red
        } else if state.alerts.iter().any(|a| a.level == 2) {
            Color::Yellow
        } else {
            Color::Cyan
        };
        (format!(" ⚠ 경보: {}", parts.join("  ")), Style::default().fg(color))
    };
    let alert_banner = Paragraph::new(Span::styled(alert_text, alert_style))
        .block(Block::default().borders(Borders::ALL).title("시장경보 (Phase B-5)"));
    f.render_widget(alert_banner, chunks[1]);

    // 호가창 — 매도(위) / 매수(아래)
    let mut rows: Vec<Row> = Vec::new();
    for a in state.asks.iter().rev() {
        rows.push(Row::new(vec![
            Cell::from(""),
            Cell::from(format!("{:.0}", a.price)).style(Style::default().fg(Color::Red)),
            Cell::from(format!("{}", a.qty)),
        ]));
    }
    for b in &state.bids {
        rows.push(Row::new(vec![
            Cell::from(format!("{}", b.qty)),
            Cell::from(format!("{:.0}", b.price)).style(Style::default().fg(Color::Blue)),
            Cell::from(""),
        ]));
    }
    let table = Table::new(
        rows,
        [Constraint::Length(10), Constraint::Length(10), Constraint::Length(10)],
    )
    .header(Row::new(vec!["매수잔량", "호가", "매도잔량"]).style(Style::default().add_modifier(Modifier::BOLD)))
    .block(Block::default().borders(Borders::ALL).title("호가창 (Order Book)"));
    f.render_widget(table, chunks[2]);

    // 포지션 + P&L + 핫키
    let pnl = state.unrealized_pnl();
    let pnl_color = if pnl >= 0.0 { Color::Green } else { Color::Red };
    let footer = Paragraph::new(vec![
        Line::from(format!(
            " 포지션 {}주 │ 진입가 {:.0} │ 현재가 {:.0}",
            state.position_qty, state.entry_price, state.last_price
        )),
        Line::from(Span::styled(
            format!(" 미실현 P&L {:.0}원 ({:.2}%)", pnl, state.pnl_pct()),
            Style::default().fg(pnl_color),
        )),
        Line::from(format!(" 상태: {} │ [b]매수 [s]매도 [q]종료", state.status)),
    ])
    .block(Block::default().borders(Borders::ALL).title("포지션 / P&L"));
    f.render_widget(footer, chunks[3]);
}
