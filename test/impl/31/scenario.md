# iter-31 시나리오: Phase B-1+B-3 + 종목 DB 동적화

## 구현 목표

### A. Phase B-1 — KRX 시장경보 종목 수집기
- KRX KIND(공시시스템) POST 스크래핑으로 투자주의/경고/위험/정리매매 종목 수집
- DB 모델: `MarketAlertDaily` (ticker, date, level, name, UniqueConstraint)
- 서비스: `KrxMarketAlertService` (graceful fallback → 빈 리스트)
- 적재: `alert_store.upsert_alerts()` / `get_active_alerts()`
- API: `GET /krx/market-alerts`, `POST /krx/market-alerts/sync`

### B. Phase B-3 — 공매도 일별 통계 수집
- KRX OPEN API `stk_smls_trd_by_isu` (공매도 거래실적 종목별)
- DB 모델: `ShortSellingDaily` (ticker, date, short_vol, short_val, short_ratio)
- 적재: `shortsell_store.upsert_short_selling()`
- API: `GET /krx/short-selling/{ticker}`

### C. 종목 DB 동적화 (사용자 요청: 지니언스 KOSDAQ 등 미등록 종목 지원)
- 기존: 165개 정적 목록 (stocks.ts)
- 개선: FinanceDataReader `StockListing(KOSPI/KOSDAQ)` — 전종목 24h 캐시
- API: `GET /krx/stocks/search?q=&market=&limit=`, `GET /krx/stocks/{ticker}`
- BFF: `GET /api/stocks/search`, `GET /api/stocks/:ticker` 프록시
- Next.js API route: `/api/stocks/search`, `/api/stocks/[ticker]`
- TopBar: BFF 동적 검색 우선 (로컬 fallback)
- page.tsx: market badge 동적화 (KOSPI 파란색 / KOSDAQ 초록색)
- 코드 옆 금액 → 기업명 표시 (이전 iter-30 완료분 포함)

## 생성/수정 파일

| 파일 | 변경 |
|---|---|
| `services/ingest/app/db.py` | MarketAlertDaily + ShortSellingDaily 모델 추가 |
| `services/ingest/app/services/market_alert_service.py` | 신규: KIND 스크래퍼 |
| `services/ingest/app/services/alert_store.py` | 신규: upsert_alerts, get_active_alerts |
| `services/ingest/app/services/shortsell_store.py` | 신규: upsert_short_selling, get_short_selling |
| `services/ingest/app/services/krx_openapi.py` | get_short_selling() 추가 |
| `services/ingest/app/api/krx.py` | stocks/search, stocks/{ticker}, market-alerts, short-selling 엔드포인트 |
| `services/ingest/tests/test_market_alert_shortsell.py` | 신규: 24개 테스트 |
| `web/apps/bff/src/proxy/proxy.controller.ts` | stocks/search, stocks/:ticker 엔드포인트 |
| `web/apps/bff/src/proxy/proxy.service.ts` | stocksSearch() 메서드 |
| `web/apps/dashboard/app/api/stocks/search/route.ts` | 신규: Next.js API route |
| `web/apps/dashboard/app/api/stocks/[ticker]/route.ts` | 신규: Next.js API route |
| `web/apps/dashboard/app/page.tsx` | market badge 동적화 + BFF meta 조회 |
| `web/apps/dashboard/components/TopBar.tsx` | handleChange async + BFF 동적 검색 |
| `web/apps/dashboard/lib/api.ts` | StockMeta 타입 + getStockMeta() |

## 시험 항목

### T1. DB 스키마
- `market_alert_daily` / `short_selling_daily` 테이블 생성 확인
- 컬럼 목록 검증

### T2. alert_store
- upsert_alerts: 정상 저장/중복 무시/빈 입력/잘못된 날짜/빈 ticker
- get_active_alerts: 전체/ticker 필터/없는 ticker

### T3. shortsell_store
- upsert/중복/empty/SELECT 최신순

### T4. KrxMarketAlertService (mock HTTP)
- 정상 파싱/네트워크 오류 → 빈 리스트/날짜 포맷 변환

### T5. API (mock 함수)
- GET /krx/market-alerts → 200
- GET /krx/market-alerts?fetch=true → 200
- POST /krx/market-alerts/sync → 200, status=ok
- GET /krx/short-selling/005930 → 200

### T6. TypeScript 컴파일
- `npx tsc --noEmit` → 오류 없음

**합계: 24개(Python) + 68개(Web) = 92개 PASS**
