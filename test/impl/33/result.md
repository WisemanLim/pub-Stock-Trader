# iter-33 결과: Phase C 고급 분석

## 판정: PASS ✅

## 시험 결과

### Python/analysis (C-1/C-2/C-5 신규, 137 전체)
```
test_health                     ... ok
test_indicators_ok              ... ok
test_indicators_vwap_field      ... ok  [NEW C-1]
test_breadth_ok                 ... ok  [NEW C-2]
test_breadth_unknown_market     ... ok  [NEW C-2]
test_openapi_routes             ... ok  (updated: /breadth/ 추가)
test_screener_ok                ... ok
test_screener_rsi_filter        ... ok
test_screener_signal_filter     ... ok  [NEW C-5]
test_screener_close_range       ... ok  [NEW C-5]
test_screener_limit_cap         ... ok  [NEW C-5]
... (기존 포함)

137 passed, 5 warnings
```

### Python/agents (C-3/C-4 신규, 39 전체)
```
test_health                             ... ok
test_personas                           ... ok
test_analyze_buy_signal                 ... ok  (updated: 6-agent, confidence 0.85)
test_analyze_persona_weight_cap         ... ok
test_analyze_unknown_persona            ... ok
test_flow_agent_note_present            ... ok  [NEW C-3]
test_alert_agent_note_present           ... ok  [NEW C-4]
test_alert_danger_overrides_signal      ... ok  [NEW C-4]
test_analyze_degraded                   ... ok
... (기타 test_control/notify/self_correction)

39 passed, 1 warning
```

### Python/ingest (변동 없음, 168 전체)
```
168 passed, 32 warnings
```

### Python/rag (변동 없음, 6 통과)
```
6 passed, 4 skipped, 1 warning
```

### Rust/workspace (변동 없음, 90 전체)
```
risk-engine: 81 passed; 1 ignored
tui-test:      9 passed
```

### Web/dashboard (C-1 UI 추가, 68 전체)
```
Tests  68 passed (68)
```

### Web/BFF (변동 없음, 10 전체)
```
Tests  10 passed (10)
```

### TypeScript
```
pnpm tsc --noEmit → 오류 없음
```

## 전체 테스트 현황

| 서비스 | 이전 | 이번 | 증감 |
|--------|------|------|------|
| Python/analysis | 131 | 137 | +6 |
| Python/agents | 36 | 39 | +3 |
| Python/ingest | 168 | 168 | 0 |
| Python/rag | 6 | 6 | 0 |
| Rust/workspace | 90 | 90 | 0 |
| Web/dashboard | 68 | 68 | 0 |
| Web/BFF | 10 | 10 | 0 |
| **합계** | **520** | **529** | **+9** |

## 구현 완료 내용

### C-1: VWAP(20) + close_pct 지표
- `indicators.py`: VWAP = (typical_price × volume 20일 롤링합) / (volume 20일 롤링합)
- `close_pct` = (close - low) / (high - low): 0.0(저가 근처) ~ 1.0(고가 근처)
- `IndicatorsResponse` 스키마: `vwap_20: float | None`, `close_pct: float | None`

### C-2: 시장 폭(Market Breadth) API
- `GET /breadth/?market=KOSPI|KOSDAQ|KRX`
- 100종목 샘플 기준, 30분 캐시
- advancing/declining/unchanged 종목수, AD Line, TRIN(Arms Index) 반환

### C-3: FlowAgent (수급 분석)
- `_flow_agent(ticker)`: ingest `/krx/investor-flow/{ticker}` 최근 3일 조회
- 기관 + 외인 모두 순매수 → BUY / 순매도 → SELL / 혼조 → HOLD
- 수급 시그널 = 지표 시그널 → confidence +0.05 / 반대 → -0.05

### C-4: AlertAgent (시장경보)
- `_alert_agent(ticker)`: ingest `/krx/market-alerts?ticker={ticker}` 조회
- 레벨 맵: 주의=1, 경고=2, 위험/위험예고=3, 정리매매=4
- 레벨≥3 → override="SELL", 레벨=2 → override="HOLD"
- 경보 레벨≥2 → confidence -0.10

### C-5: 스크리너 확장 (80종목)
- `signal`, `min_close`, `max_close` 필터 추가
- `head(50)` → `head(80)` 종목 확대
- limit 상한 80으로 클리핑

### C-6: 공매도 비율 스크리너
- `max_short_ratio` 필터: ingest에서 short_ratio 조회 후 필터링
- `ScreenerResult.short_ratio: float | None`

### 6-에이전트 파이프라인
- `run_pipeline()`: Scraper → Analyst → Portfolio → **FlowAgent → AlertAgent** → Decision
- notes 길이: 4 → 6

### Web 대시보드
- `shortSell.rows ?? []` 방어 처리로 런타임 TypeError 수정
- 기술지표 패널: VWAP(20) 행, Close% 행 추가
- `format.ts`: `vwap_20`, `close_pct` 타입 추가

## 비고
- FlowAgent/AlertAgent 장애 시 graceful degrade (`available: false`, `alert_level: 0`)
- 시장경보 override 우선순위: alert override > 지표 signal
- VWAP(20)은 데이터 부족 시 None 반환 (20일 미만 데이터)
