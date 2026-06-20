# Iter 27 시험 결과

판정: **PASS**
일시: 2026-06-18

---

## 시험 1 — 캔들차트 툴팁 수정 (Web)

| # | 항목 | 결과 |
|---|------|------|
| 1 | vitest 22개 전체 | ✅ PASS |
| 2 | TypeScript `tsc --noEmit` | ✅ OK |
| 3 | `CandleTooltip` → `position:fixed` + viewport 좌표 | ✅ 수정 완료 |
| 4 | `zIndex:9999`, `pointerEvents:none` | ✅ 적용 |
| 5 | 오른쪽 경계 flip 로직 | ✅ 적용 |

**수정 핵심**: `position:absolute` + `containerWidth=720(SVG 자연폭)` 비교 오류 →
`position:fixed` + `clientX/clientY` (viewport 좌표)로 교체. overflow·stacking 문제 해소.

---

## 시험 2 — KRX OPEN API 서비스 (Ingest Python)

```
uv run pytest tests/test_krx_openapi.py -v
23 passed in 0.28s
```

| 그룹 | 테스트 수 | 결과 |
|------|----------|------|
| TestHelpers (변환 헬퍼) | 7 | ✅ PASS |
| TestKrxServiceUnconfigured | 3 | ✅ PASS |
| TestKrxServiceConfigured | 8 | ✅ PASS |
| TestKrxEndpoints | 5 | ✅ PASS |
| **소계** | **23** | **PASS** |

전체 ingest suite: `128 passed` ← 기존 105 + 신규 23.

---

## 전체 테스트 집계

| 영역 | 이전 | 이번 | 증감 |
|------|------|------|------|
| Web (vitest) | 22 | 22 | — |
| Ingest (pytest) | 105 | 128 | +23 |
| **합계** | **127** | **150** | **+23** |

---

## 변경 파일

| 파일 | 내용 |
|------|------|
| `web/apps/dashboard/components/CandleChart.tsx` | 툴팁 `position:fixed` + viewport 좌표 수정 |
| `services/ingest/app/core/config.py` | `krx_open_api_key`, `krx_api_rate_limit` 추가 |
| `services/ingest/app/services/krx_openapi.py` | KRX OPEN API 클라이언트 (신규) |
| `services/ingest/app/api/krx.py` | `/krx/status`, `/krx/ohlcv/{ticker}`, `/krx/investor-flow/{ticker}` (신규) |
| `services/ingest/app/main.py` | `krx` 라우터 등록 |
| `services/ingest/tests/test_krx_openapi.py` | 23개 테스트 (신규) |
| `test/impl/27/scenario.md` | 시험 시나리오 |
| `test/impl/27/result.md` | 이 파일 |

---

## 비고

- KRX OPEN API 키 미설정 시 빈 결과 반환 — FinanceDataReader 폴백 유지됨.
- 실 키 주입: `KRX_OPEN_API_KEY` 환경변수 (Keychain/Vault 경유, 파일 기재 금지).
- 투자자 수급 엔드포인트 (`/krx/investor-flow/`) `phase:"A_pending"` 표시 — BFF/대시보드 연동은 Phase B.
