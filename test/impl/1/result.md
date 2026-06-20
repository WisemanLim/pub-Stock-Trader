# test/impl/1 — F1 ingest 서비스 시험 결과

**판정: PASS**  
**일시: 2026-06-06**  
**러너**: pytest 9.0.3, Python 3.13.12 (uv venv)  
**실행**: `cd services/ingest && uv run pytest tests/ -v`

## 결과 표

| TC | 이름 | 결과 | 비고 |
|----|------|------|------|
| TC-01 | 헬스체크 `GET /health` | ✅ PASS | status=ok, service=ingest |
| TC-02 | 종가 조회 정상 | ✅ PASS | price=73500.0, volume=1200000 |
| TC-03 | ticker 대문자 정규화 | ✅ PASS | aapl → AAPL |
| TC-04 | 종가 데이터 없음 (404) | ✅ PASS | HTTP 404, detail 필드 |
| TC-05 | OHLCV 조회 정상 | ✅ PASS | count=5, bars 구조 검증 |
| TC-06 | OHLCV 빈 응답 | ✅ PASS | count=0, bars=[] |
| TC-07 | OpenAPI 스키마 등록 | ✅ PASS | 3개 엔드포인트 확인 |
| TC-08 | Redis 미설정 부분 장애 허용 | ✅ PASS | API 200 정상 응답 |
| TC-09 | timestamp ISO 8601 형식 | ✅ PASS | YYYY-MM-DDTHH:MM:SS 형식 |

## 요약

```
9 passed, 1 warning in 0.16s
```

경고: `StarletteDeprecationWarning` — httpx → httpx2 마이그레이션 권고(기능 영향 없음).

## 픽스 이력

- pyproject.toml: `FinanceDataReader` → `finance-datareader` (PyPI 공식 패키지명 수정)
