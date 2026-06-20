# iter-32 시나리오: Phase B 완성 (B-2, B-4, B-5, B-6) + MACD 지표 버그 수정

## 구현 목표

### A. Phase B-2 — 시장경보 긴급청산 트리거 (Rust risk-engine)
- `RiskRequest` 확장: `market_alert_level: u8` (0=정상, 1=주의, 2=경고, 3=위험/정리매매)
- 규칙: level >= 3 → ForceSell (긴급청산), level == 2 → BlockBuy (신규매수 차단)
- 신규 엔드포인트: `POST /risk/alert-check` (명시적 B-2 경로, 기존 evaluate 로직 동일)

### B. Phase B-4 — 공매도 과열 포지션 축소 로직 (risk-engine)
- `RiskRequest` 확장: `short_ratio: f64`, `short_ratio_limit: f64`
- 규칙: `short_ratio > short_ratio_limit && limit > 0` → ReducePosition (포지션 축소)
- 우선순위: ForceSell > TakeProfit > BlockBuy > ReducePosition(short_sell_excess 포함)

### C. Phase B-5 — TUI 시장경보 배너 + 공매도 컬럼 (apps/tui)
- `model.rs`: `AlertItem { ticker, level, name }` + `AppState.alerts` + `AppState.short_ratio`
- `main.rs`: 레이아웃에 `Constraint::Length(3)` 배너 행 추가 (헤더/호가창 사이)
- 배너: 경보 없음 → 초록색 ✓, 경고 → 노랑, 위험 → 빨강
- 헤더: 공매도 비율 추가 표시

### D. Phase B-6 — 웹 대시보드 시장경보/공매도 패널 실데이터 연결
- `GET /api/market-alerts` Next.js API route → BFF → ingest
- `GET /api/short-selling/[ticker]` Next.js API route → BFF → ingest
- BFF proxy: `marketAlerts()`, `shortSelling(ticker)` 메서드 추가
- `page.tsx`: 시장경보 패널 실데이터 (레벨별 배지, 종목목록, caution/warning/danger 집계)
- `page.tsx`: 공매도 패널 실데이터 (날짜별 비율, 색상코딩)

### E. MACD 지표 버그 수정 (사용자 요청)
- 원인: `DashboardSnapshot.indicators.macd` 타입이 `number`로 잘못 정의됨
  (실제 API 응답: `{ macd: number, signal: number, histogram: number }`)
- 수정: `format.ts` 타입 정의 수정
- `bb_upper/bb_lower` → `bollinger.upper/lower` (실제 필드명)
- `macd_signal` → `macd.signal` (중첩 객체)
- `sma_20` → `sma_50` (실제 API 필드명)
- 히스토그램 행 추가

## 생성/수정 파일

| 파일 | 변경 |
|---|---|
| `core/risk-engine/src/risk.rs` | market_alert_level + short_ratio 필드/규칙/테스트 9개 추가 |
| `core/risk-engine/src/main.rs` | `/risk/alert-check` 엔드포인트 추가 |
| `apps/tui/src/model.rs` | AlertItem 구조체 + AppState.alerts/short_ratio 추가 |
| `apps/tui/src/main.rs` | 시장경보 배너 행 + 공매도 비율 헤더 표시 |
| `web/apps/bff/src/proxy/proxy.controller.ts` | market-alerts, short-selling 엔드포인트 추가 |
| `web/apps/bff/src/proxy/proxy.service.ts` | marketAlerts(), shortSelling() 메서드 추가 |
| `web/apps/dashboard/app/api/market-alerts/route.ts` | 신규: BFF 프록시 |
| `web/apps/dashboard/app/api/short-selling/[ticker]/route.ts` | 신규: BFF 프록시 |
| `web/apps/dashboard/app/page.tsx` | 시장경보/공매도 패널 실데이터 + 타입 수정 |
| `web/apps/dashboard/lib/format.ts` | DashboardSnapshot indicators 타입 수정 (MACD 버그) |

## 시험 항목

### T1. Rust risk-engine — 신규 규칙 (9개)
- `market_alert_danger_force_sell`: level=3 → ForceSell
- `market_alert_level4_also_danger`: level=4 → ForceSell
- `market_alert_warning_blocks_buy`: level=2 → BlockBuy
- `market_alert_caution_no_action`: level=1 → Hold
- `market_alert_zero_normal`: level=0(default) → Hold
- `short_sell_excess_reduces_position`: ratio > limit → ReducePosition
- `short_sell_below_limit_no_action`: ratio < limit → Hold
- `short_sell_limit_zero_disabled`: limit=0 → Hold (규칙 비활성)
- `market_alert_danger_overrides_short_sell`: danger + excess → ForceSell 우선

### T2. Rust 기존 규칙 — 회귀
- 10개 기존 risk 테스트 이상 없음

### T3. TUI 컴파일
- `cargo build` 성공 (model + main 변경)

### T4. TypeScript 컴파일
- `npx tsc --noEmit` → 오류 없음 (format.ts 타입 수정 반영)

### T5. Web 단위 테스트
- 68개 기존 테스트 이상 없음

**합계: 81 Rust + 168 Python + 68 Web = 317개 PASS (iter 신규: +9 Rust risk)**
