# iter-32 결과: Phase B 완성 + MACD 버그 수정

## 판정: PASS ✅

## 시험 결과

### Rust/risk-engine (9 신규, 81 전체)
```
test risk::tests::hold_when_all_pass ... ok
test risk::tests::market_alert_caution_no_action ... ok  [NEW]
test risk::tests::market_alert_danger_force_sell ... ok  [NEW]
test risk::tests::market_alert_danger_overrides_short_sell ... ok  [NEW]
test risk::tests::market_alert_level4_also_danger ... ok  [NEW]
test risk::tests::market_alert_warning_blocks_buy ... ok  [NEW]
test risk::tests::market_alert_zero_normal ... ok  [NEW]
test risk::tests::short_sell_below_limit_no_action ... ok  [NEW]
test risk::tests::short_sell_excess_reduces_position ... ok  [NEW]
test risk::tests::short_sell_limit_zero_disabled ... ok  [NEW]
... (기존 10개 + paper 62개 포함)

test result: ok. 81 passed; 0 failed; 1 ignored
```

### TUI 빌드
```
cargo build → 성공 (model.rs AlertItem + AppState 확장, main.rs 배너 추가)
```

### Python/ingest (변동 없음, 168 전체)
```
168 passed, 32 warnings in 0.64s
```

### Web/dashboard (변동 없음, 68 전체)
```
Tests  68 passed (68)
```

### TypeScript
```
npx tsc --noEmit → 오류 없음
```

## 전체 테스트 현황

| 서비스 | 이전 | 이번 | 증감 |
|--------|------|------|------|
| Rust/risk-engine | 72 | 81 | +9 |
| Python/ingest | 168 | 168 | 0 |
| Web | 68 | 68 | 0 |
| tools/mpm | 17 | 17 | 0 |
| **합계** | **511** | **520** | **+9** |

## 구현 완료 내용

### Phase B-2 (시장경보 긴급청산)
- `RiskRequest.market_alert_level`: 0=정상, 1=주의, 2=경고, 3≥=위험/정리매매
- level≥3 → ForceSell, level=2 → BlockBuy
- `POST /risk/alert-check` 엔드포인트 신규 추가

### Phase B-4 (공매도 과열 포지션 축소)
- `RiskRequest.short_ratio` / `short_ratio_limit`
- ratio > limit && limit > 0 → ReducePosition (포지션 축소)
- limit=0 시 규칙 비활성 (기존 호환 유지)

### Phase B-5 (TUI 시장경보 배너)
- `AlertItem { ticker, level, name }` 구조체 추가
- `AppState.alerts: Vec<AlertItem>`, `AppState.short_ratio: f64` 추가
- 레이아웃 4단: 헤더 + **시장경보 배너** + 호가창 + 포지션/P&L
- 배너 색상: 위험=빨강, 경고=노랑, 주의=파랑, 정상=초록
- 헤더에 공매도 비율(%) 실시간 표시

### Phase B-6 (웹 대시보드 실데이터 연결)
- `GET /api/market-alerts` → BFF → ingest `/krx/market-alerts`
- `GET /api/short-selling/[ticker]` → BFF → ingest `/krx/short-selling/{ticker}`
- 시장경보 패널: 레벨 배지(위험/경고/주의 색상) + 종목목록 + 집계 카운트
- 공매도 패널: 날짜별 비율 표(20%초과=빨강, 10%초과=노랑) + 최근비율 표시
- graceful fallback: BFF 미기동 시 빈 데이터 표시

### MACD 지표 버그 수정
- `DashboardSnapshot.indicators.macd`: `number` → `{macd, signal, histogram}` 객체
- `ind.macd` → `ind.macd?.macd` (값 표시)
- `ind.macd_signal` → `ind.macd?.signal` (Signal 행)
- `Hist` 행 추가 (histogram 표시)
- `ind.bb_upper/bb_lower` → `ind.bollinger?.upper/lower`
- `ind.sma_20` → `ind.sma_50` (API 실제 필드명)

## 비고
- 시장경보 배너/공매도 패널은 ingest 서비스 기동 시 실데이터 표시, 미기동 시 graceful fallback
- `/risk/alert-check`는 `/risk/check`와 동일 로직 (명시적 B-2 경로 추가)
- MACD `[object Object]` 렌더링 버그 수정 완료
