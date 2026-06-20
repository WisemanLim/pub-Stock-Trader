# iter-30 시나리오: Phase A-2 — 일별 배치 스케줄러 + DB 스키마

## 구현 목표

### A. SQLAlchemy DB 스키마 확장
- `ohlcv_daily` 테이블: ticker, date, OHLCV, volume, change_pct, source
- `investor_flow_daily` 테이블: ticker, date, institution/foreign/individual 순매수
- UniqueConstraint(ticker, date) — INSERT OR IGNORE 방식 중복 방어

### B. OHLCV 적재 서비스 (ohlcv_store)
- `upsert_ohlcv(ticker, rows)` → int (저장 건수)
- `upsert_investor_flow(ticker, rows)` → int
- `latest_ohlcv_date(ticker)` → date | None
- 날짜 포맷 YYYYMMDD / YYYY-MM-DD 모두 지원
- 중복 입력 시 0 반환 (IntegrityError 무시)

### C. APScheduler 배치 스케줄러
- `BackgroundScheduler` + `CronTrigger`(평일 15:40 KST)
- `start()` / `stop()` / `run_now()` / `status()`
- KRX_OPEN_API_KEY 미설정 시 skipped 반환 (graceful)
- FastAPI `lifespan` 훅으로 시작/종료

### D. 스케줄러 관리 API
- `GET /scheduler/status` — 스케줄러 상태 + 마지막 실행 결과
- `POST /scheduler/run` — 수동 즉시 실행

## 생성/수정 파일

| 파일 | 변경 |
|---|---|
| `services/ingest/app/db.py` | 신규: OhlcvDaily, InvestorFlowDaily 모델 |
| `services/ingest/app/services/ohlcv_store.py` | 신규: upsert 함수 3개 |
| `services/ingest/app/services/batch_scheduler.py` | 신규: APScheduler 래퍼 |
| `services/ingest/app/api/scheduler.py` | 신규: /scheduler 라우터 |
| `services/ingest/app/core/config.py` | 스케줄러 설정 4개 추가 |
| `services/ingest/app/main.py` | lifespan 훅 + 라우터 등록 |
| `services/ingest/pyproject.toml` | sqlalchemy + apscheduler 의존성 |
| `services/ingest/tests/test_batch_scheduler.py` | 신규: 16개 테스트 |

## 시험 항목

### T1. DB 스키마
- `ohlcv_daily` 테이블 생성 확인
- `investor_flow_daily` 테이블 생성 확인
- 컬럼 목록 검증 (ticker, date, open, high, low, close, volume)

### T2. upsert 동작
- 신규 2행 저장 → saved=2
- 빈 리스트 → saved=0
- 중복 입력 → saved=0 (INSERT OR IGNORE)
- 잘못된 날짜 → saved=0
- latest_ohlcv_date() 정확성
- ISO 날짜 포맷(YYYY-MM-DD) 지원

### T3. 스케줄러 API
- GET /scheduler/status → 200, running/last_run/tickers 포함
- POST /scheduler/run → 200 (skipped or ok)
- schedule 필드 "KST" 포함
- KRX_OPEN_API_KEY 미설정 시 run → 200

**합계: 16개 PASS**
