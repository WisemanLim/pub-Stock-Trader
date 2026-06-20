# test/impl/1 — F1 ingest 서비스 시험 시나리오

**대상**: `services/ingest` — F1.1 시세·OHLCV·종목목록 REST API  
**차수**: 1  
**러너**: pytest 9.x + httpx TestClient  
**의존 격리**: FinanceDataReader → unittest.mock.patch 대체 (네트워크 불필요)

## 시나리오

### TC-01 헬스체크
- 요청: `GET /health`
- 기대: `{"status": "ok", "service": "ingest"}`
- 검증: HTTP 200, `status` 필드

### TC-02 종가 조회 (정상)
- 요청: `GET /market/price/005930`
- 조건: mock DataFrame 마지막 행 = Close 73500.0, Volume 1200000
- 기대: `ticker=005930, price=73500.0, volume=1200000, source=FinanceDataReader`

### TC-03 ticker 대문자 정규화
- 요청: `GET /market/price/aapl` (소문자)
- 기대: 응답 `ticker == "AAPL"`

### TC-04 종가 조회 — 데이터 없음 (404)
- 요청: `GET /market/price/INVALID`
- 조건: mock → 빈 DataFrame
- 기대: HTTP 404, `detail` 필드

### TC-05 OHLCV 조회 (정상)
- 요청: `GET /market/ohlcv/005930?days=5`
- 기대: `count=5`, bars[0].close=70500.0, 모든 필드(date/open/high/low/close/volume) 존재

### TC-06 OHLCV — 빈 응답
- 요청: `GET /market/ohlcv/UNKNOWN`
- 조건: mock → 빈 DataFrame
- 기대: HTTP 200, `count=0`, `bars=[]`

### TC-07 OpenAPI 스키마 엔드포인트 등록 확인
- 요청: `GET /openapi.json`
- 기대: paths 에 `/market/price/{ticker}`, `/market/ohlcv/{ticker}`, `/market/tickers/{market}` 포함

## 금융 규제 추가 케이스 (COMPLIANCE.md — 전자금융감독규정·ISMS-P)

### TC-08 멱등키 — Redis publish 실패 무시
- 조건: Redis URL 미설정 환경(`REDIS_URL` 없음) — 기본 `TestClient` 환경
- 기대: `publish_tick` 반환 False, 그러나 API 응답은 정상(200) — 부분 장애 허용
- 근거: 실시간 스트림 장애가 REST 조회를 차단하지 않아야 함.

### TC-09 시세 응답 timestamp 형식
- 기대: `timestamp` 필드 ISO 8601 형식 (`YYYY-MM-DDTHH:MM:SS`)
- 근거: 감사 로그·정산 대사 시 시각 명확성 필요 (전자금융거래법 §22 거래기록 보존).
