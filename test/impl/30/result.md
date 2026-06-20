# iter-30 결과: Phase A-2 — 일별 배치 스케줄러 + DB 스키마

## 판정: PASS ✅

## 시험 결과

```
services/ingest/tests/test_batch_scheduler.py — 16/16 PASS
TestDbSchema::test_ohlcv_daily_table_created            PASSED
TestDbSchema::test_investor_flow_table_created          PASSED
TestDbSchema::test_ohlcv_columns                        PASSED
TestOhlcvStore::test_upsert_ohlcv_returns_saved_count   PASSED
TestOhlcvStore::test_upsert_ohlcv_empty_rows            PASSED
TestOhlcvStore::test_upsert_ohlcv_duplicate_ignored     PASSED
TestOhlcvStore::test_upsert_ohlcv_bad_date_skipped      PASSED
TestOhlcvStore::test_latest_ohlcv_date_after_upsert     PASSED
TestOhlcvStore::test_latest_ohlcv_date_none_when_empty  PASSED
TestOhlcvStore::test_upsert_investor_flow               PASSED
TestOhlcvStore::test_upsert_investor_flow_duplicate_ignored PASSED
TestOhlcvStore::test_upsert_ohlcv_iso_date_format       PASSED
TestSchedulerApi::test_status_endpoint                  PASSED
TestSchedulerApi::test_run_endpoint_returns_result      PASSED
TestSchedulerApi::test_status_has_schedule_info         PASSED
TestSchedulerApi::test_run_skipped_when_no_api_key      PASSED

전체: 144/144 PASS (ingest 128→144)
```

## 전체 테스트 현황

| 서비스 | 이전 | 이번 | 증감 |
|--------|------|------|------|
| Python/ingest | 128 | 144 | +16 |
| Python/analysis | 계속 | 동일 | - |
| Rust | 81 | 81 | 0 |
| Web | 68 | 68 | 0 |
| tools/mpm | 17 | 17 | 0 |
| **합계** | **471** | **487** | **+16** |

## 구현 완료 내용

- `app/db.py`: OhlcvDaily + InvestorFlowDaily SQLAlchemy 모델, init_db(), get_session()
- `app/services/ohlcv_store.py`: upsert_ohlcv, upsert_investor_flow, latest_ohlcv_date
- `app/services/batch_scheduler.py`: BackgroundScheduler (평일 15:40 KST), run_now, status
- `app/api/scheduler.py`: GET /scheduler/status, POST /scheduler/run
- `app/core/config.py`: scheduler_enabled, scheduler_tickers, scheduler_hour, scheduler_minute
- `app/main.py`: FastAPI lifespan 훅 (init_db + scheduler start/stop)
- `pyproject.toml`: sqlalchemy>=2.0, apscheduler>=3.10,<4

## 비고

- KRX_OPEN_API_KEY 미설정 환경에서 배치 실행 시 `status=skipped` 반환 (graceful fallback)
- SQLite UniqueConstraint(ticker, date) + IntegrityError catch = INSERT OR IGNORE 동작
- APScheduler BackgroundScheduler: 동기 KRX API 호출이 asyncio 루프를 차단하지 않도록 스레드 분리
