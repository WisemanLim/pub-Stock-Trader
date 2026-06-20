# iter-33 시나리오: Phase C 고급 분석

## 범위

| 항목 | 설명 |
|------|------|
| C-1 | VWAP(20) + close_pct 지표 추가 (analysis) |
| C-2 | 시장 폭 API: 상승/하락/보합 종목수, TRIN, AD Line |
| C-3 | 수급 분석 에이전트 (FlowAgent): 기관·외인 순매수 방향 |
| C-4 | 시장경보 에이전트 (AlertAgent): 경보 레벨 시그널 override |
| C-5 | 스크리너 확장: signal/close 범위/limit 80 필터 |
| C-6 | 스크리너 공매도 비율(short_ratio) 필터 |
| Web | VWAP/Close% 대시보드 지표 패널 표시 |
| Fix | shortSell.rows undefined 런타임 오류 수정 |

## 시나리오 1: C-1 VWAP/close_pct

```
GET /indicators/{ticker}
기대: vwap_20 (float | null), close_pct (0.0 ~ 1.0) 포함
```

## 시나리오 2: C-2 시장 폭

```
GET /breadth/?market=KOSPI
기대: advancing, declining, unchanged, trin, ad_line, market, sample

GET /breadth/?market=UNKNOWN
기대: 200 + sample=0 (degrade)
```

## 시나리오 3: C-3 FlowAgent

```
POST /agents/analyze {"ticker": "005930", "persona": "swing"}
기대:
  - notes[3].agent == "FlowAgent"
  - FlowAgent.data.available == true
  - FlowAgent.data.institutional_net > 0 (mock: 기관 3일 순매수 합계 +75000)
  - FlowAgent.data.signal == "BUY"
  - decision.confidence == 0.85 (기본 0.80 + 수급 동일방향 +0.05)
```

## 시나리오 4: C-4 AlertAgent 정상

```
POST /agents/analyze {"ticker": "005930", "persona": "swing"}
기대:
  - notes[4].agent == "AlertAgent"
  - AlertAgent.data.alert_level == 0
  - AlertAgent.data.override == null
```

## 시나리오 5: C-4 AlertAgent 위험경보 override

```
mock: /krx/market-alerts → 투자위험 레벨 반환
POST /agents/analyze {"ticker": "005930", "persona": "swing"}
기대:
  - AlertAgent.data.alert_level == 3
  - AlertAgent.data.override == "SELL"
  - decision.signal == "SELL" (지표가 BUY여도 경보 override)
```

## 시나리오 6: C-5 스크리너 확장 필터

```
POST /screener/ {"market": "KRX", "signal": "HOLD", "limit": 10}
기대: 모든 결과 signal == "HOLD"

POST /screener/ {"min_close": 70000, "max_close": 80000}
기대: 모든 결과 70000 ≤ close ≤ 80000

POST /screener/ {"limit": 200}
기대: 정상 응답 (내부 min(200, 80) 적용)
```

## 시나리오 7: 6-에이전트 파이프라인 구성

```
기대: notes 길이 == 6
agents 순서: ["Scraper", "Analyst", "Portfolio", "FlowAgent", "AlertAgent", "Decision"]
```

## 시나리오 8: Web 오류 수정 — shortSell.rows undefined

```
page.tsx line 75: raw.rows ?? [] 방어 처리
기대: shortSell.rows 항상 배열 (API 응답 shape 불일치 시에도 안전)
```

## 시나리오 9: Web VWAP 지표 표시

```
기술지표 패널에 VWAP(20) 및 Close% 행 추가
format.ts DashboardSnapshot.indicators에 vwap_20, close_pct 타입 추가
```
