# iter-31 결과: Phase B-1+B-3 + 종목 DB 동적화

## 판정: PASS ✅

## 시험 결과

### Python/ingest (24 신규, 168 전체)
```
tests/test_market_alert_shortsell.py — 24/24 PASS
TestDbSchema (4): market_alert/short_selling 테이블+컬럼 확인
TestAlertStore (8): upsert/중복/날짜오류/빈ticker/get 전체/필터
TestShortSellStore (5): upsert/중복/empty/SELECT 최신순
TestMarketAlertService (3): 정상파싱/네트워크오류/날짜포맷
TestMarketAlertApi (4): 4개 엔드포인트 200 확인 (store mock)

전체 ingest: 168/168 PASS
```

### Web/dashboard (68 전체, 변동 없음)
```
candles.spec.ts: 19 PASS
tooltips.spec.ts: 28 PASS
stocks.spec.ts: 16 PASS
format.spec.ts: 5 PASS
합계: 68/68 PASS
```

### TypeScript
```
npx tsc --noEmit → 오류 없음
```

## 전체 테스트 현황

| 서비스 | 이전 | 이번 | 증감 |
|--------|------|------|------|
| Python/ingest | 144 | 168 | +24 |
| Rust | 81 | 81 | 0 |
| Web | 68 | 68 | 0 |
| tools/mpm | 17 | 17 | 0 |
| **합계** | **487** | **511** | **+24** |

## 구현 완료 내용

### Phase B-1 (시장경보)
- `MarketAlertDaily` DB 모델 (UniqueConstraint ticker+date+level)
- `KrxMarketAlertService`: KIND POST 스크래핑, 페이지네이션, graceful fallback
- `alert_store`: upsert/query (INSERT OR IGNORE)
- `/krx/market-alerts` GET (DB조회, fetch=true 시 실시간 수집)
- `/krx/market-alerts/sync` POST (즉시 동기화)

### Phase B-3 (공매도)
- `ShortSellingDaily` DB 모델
- `KrxOpenApiService.get_short_selling()`: stk_smls_trd_by_isu API ID
- `shortsell_store`: upsert/query
- `/krx/short-selling/{ticker}` GET

### 종목 DB 동적화
- ingest `/krx/stocks/search?q=&market=&limit=`: FDR 전종목 24h 캐시
- ingest `/krx/stocks/{ticker}`: 단일 종목 메타
- BFF `/api/stocks/search`, `/api/stocks/:ticker` 프록시 (graceful fallback)
- Next.js API route `/api/stocks/search`, `/api/stocks/[ticker]`
- TopBar: BFF 동적 검색 (2글자 이상 입력 시), 로컬 165종목 즉시 fallback
- page.tsx: market badge 동적화 (로컬→BFF 순서 조회), KOSDAQ 초록색 / KOSPI 파란색
- 코드 옆 금액 제거 → 기업명 표시

## 비고
- FDR `StockListing` 최초 호출 시 수초 소요 → 24h 메모리 캐시로 이후 즉시 응답
- BFF/ingest 미기동 시 TopBar는 로컬 165종목으로 graceful fallback
- KIND 시장경보 API 응답 포맷은 실제 연동 시 필드명 확인 필요 (`invstWarnTpNm`, `isuSrtCd`)
