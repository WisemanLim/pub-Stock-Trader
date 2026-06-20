# Iter 27 시험 시나리오

## 목적
1. 캔들차트 마우스오버 툴팁 수정 (F6.2) — `position:fixed` + viewport 좌표로 교체
2. F1.5 KRX OPEN API 수집기 구현 — `KrxOpenApiService`, `/krx/*` 엔드포인트

---

## 시험 1 — 캔들차트 툴팁 (Web)

| # | 시나리오 | 기대결과 |
|---|----------|---------|
| 1 | vitest `findCandleIndex` 6개 케이스 | 모두 PASS |
| 2 | TS 타입 오류 없음 | `tsc --noEmit` → OK |
| 3 | `CandleTooltip` → `position:fixed`, `clientX/clientY` viewport 좌표 | overflow·stacking 문제 없음 |
| 4 | 툴팁 `zIndex: 9999`, `pointerEvents: none` | 클릭·스크롤 방해 없음 |
| 5 | 오른쪽 경계 flip: `clientX + TOOLTIP_W + 16 > window.innerWidth` | 뷰포트 밖으로 안 나감 |

---

## 시험 2 — KRX OPEN API 서비스 (Ingest Python)

### 변환 헬퍼
| # | 입력 | 기대 |
|---|------|------|
| H1 | `_fmt_date("20260101")` | `"2026-01-01"` |
| H2 | `_fmt_date("2026-01-01")` | 그대로 반환 |
| H3 | `_to_int("1,200,000")` | `1200000` |
| H4 | `_to_int("N/A")` | `0` |
| H5 | `_to_float("1.48")` | `≈1.48` |
| H6 | `_to_float("-")` | `0.0` |

### 미설정(no key)
| # | 시나리오 | 기대 |
|---|----------|------|
| U1 | `KrxOpenApiService(api_key="").configured` | `False` |
| U2 | `get_daily_ohlcv(...)` 미설정 | `[]` (HTTP 호출 없음) |
| U3 | `get_investor_flow(...)` 미설정 | `[]` |

### 설정됨(mock HTTP)
| # | 시나리오 | 기대 |
|---|----------|------|
| C1 | `KrxOpenApiService(api_key="test-key").configured` | `True` |
| C2 | OHLCV 파싱: `TRD_DD/OPNPRC/HGPRC/LWPRC/CLSPRC/ACC_TRDVOL/FLUC_RT` | date, OHLCV, volume, change_pct, source 정확 |
| C3 | KOSDAQ 마켓 → api_id = `ksq_bydd_trd` | 확인 |
| C4 | KOSPI 마켓 → api_id = `stk_bydd_trd` | 확인 |
| C5 | 투자자 flow 파싱: 기관/외인/개인 순매수 | 정확 |
| C6 | 투자자 API → `stk_invsr_trd_by_isu` | 확인 |
| C7 | 불량 row → 건너뜀, 나머지 정상 파싱 | PASS |
| C8 | `_fetch` 예외 → 빈 리스트 | PASS |

### REST 엔드포인트
| # | 요청 | 기대 |
|---|------|------|
| E1 | `GET /krx/status` | 200, `configured` 키 존재 |
| E2 | `GET /krx/ohlcv/005930` (미설정) | 200, `bars=[], configured=false` |
| E3 | `GET /krx/investor-flow/005930` (미설정) | 200, `flows=[], phase="A_pending"` |
| E4 | `GET /krx/ohlcv/005930?from_date=20260101&to_date=20260131&market=KOSPI` | 200 |
| E5 | `GET /krx/ohlcv/123456?market=KOSDAQ` | 200 |
