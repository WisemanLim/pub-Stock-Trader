# Test Result — iter-34 (Phase D)

**판정: PASS**
실행일: 2026-06-18

## 테스트 결과 요약

| 서비스 | 결과 | 통과 | 실패 | 스킵 |
|--------|------|------|------|------|
| ingest | ✅ PASS | 168 | 0 | 0 |
| analysis | ✅ PASS | 137 | 0 | 0 |
| agents | ✅ PASS | 39 | 0 | 0 |
| rag | ✅ PASS | 6 | 0 | 4(skipped) |
| dashboard TS | ✅ PASS | - | 0 | - |
| bff TS | ✅ PASS | - | 0 | - |

총 Python 테스트: **350 passed, 4 skipped**

## 시나리오별 결과

### Phase D 기능 시나리오 (API 통합 — 서비스 기동 필요)

| 시나리오 | 설명 | 판정 | 비고 |
|---------|------|------|------|
| S-34-01 | ingest ESG 점수 API | ✅ IMPL | esg_store.py 구현, `/esg/{ticker}` 라우트 |
| S-34-02 | ingest ESG 캐시 | ✅ IMPL | functools.lru_cache(maxsize=512), 6h TTL |
| S-34-03 | ingest 분봉 5m | ✅ IMPL | intraday.py FDR→fallback, `/market/intraday/{ticker}?interval=5m` |
| S-34-04 | ingest 분봉 1m | ✅ IMPL | 동일 라우터, interval=1m, 60s cache |
| S-34-05 | analysis 분봉 지표 | ✅ IMPL | intraday_indicators.py RSI/MACD/VWAP |
| S-34-06 | rag IR 보고서 적재 | ✅ IMPL | POST /rag/ir-report, doc_id=ir:{ticker}:{ts} |
| S-34-07 | rag IR 보고서 조회 | ✅ IMPL | GET /rag/ir-report/{ticker}, ticker 필터 |
| S-34-08 | rag IR 미적재 종목 | ✅ IMPL | available=false 응답 |
| S-34-09 | ESG 스크리너 필터 | ✅ IMPL | screener.py min_esg_score 필터 |
| S-34-10 | ESG 스크리너 zero | ✅ IMPL | min_esg_score=None 시 패스스루 |

### BFF 라우트

| 시나리오 | 설명 | 판정 |
|---------|------|------|
| S-34-11 | BFF GET /api/esg/:ticker | ✅ PASS |
| S-34-12 | BFF GET /api/portfolio | ✅ PASS |
| S-34-13 | BFF GET /api/rag/ir-report/:ticker | ✅ PASS |

### TypeScript 컴파일 (tsc --noEmit)

| 시나리오 | 파일 | 판정 |
|---------|------|------|
| S-34-14 | strategy/page.tsx | ✅ PASS |
| S-34-15 | agents/page.tsx | ✅ PASS |
| S-34-16 | backtest/page.tsx | ✅ PASS |
| S-34-17 | risk/page.tsx | ✅ PASS |
| S-34-18 | portfolio/page.tsx | ✅ PASS |
| S-34-19 | bff tsc --noEmit | ✅ PASS |
| S-34-20 | dashboard tsc --noEmit (ESG 위젯) | ✅ PASS |

### 회귀

| 시나리오 | 설명 | 판정 |
|---------|------|------|
| S-34-R01 | ingest 전체 테스트 168개 | ✅ PASS |
| S-34-R02 | analysis 전체 테스트 137개 | ✅ PASS |
| S-34-R03 | agents 전체 테스트 39개 | ✅ PASS |

## 구현 내역

### 신규 파일
- `services/ingest/app/services/esg_store.py` — ESG 프록시 점수 계산 (E/S/G)
- `services/ingest/app/services/intraday.py` — 분봉 수집 (FDR → fallback)
- `services/ingest/app/api/esg.py` — GET /esg/{ticker}
- `services/ingest/app/api/intraday.py` — GET /market/intraday/{ticker}
- `services/analysis/app/services/intraday_indicators.py` — RSI/MACD/VWAP (분봉)
- `services/analysis/app/api/intraday_indicators.py` — GET /indicators/intraday/{ticker}
- `web/apps/dashboard/app/strategy/page.tsx` — 스크리너 서브페이지 (실제 API 연결)
- `web/apps/dashboard/app/agents/page.tsx` — 6-에이전트 파이프라인 서브페이지
- `web/apps/dashboard/app/backtest/page.tsx` — 백테스팅 서브페이지 (전략 선택/실행)
- `web/apps/dashboard/app/risk/page.tsx` — 리스크 모니터 (시장경보+공매도)
- `web/apps/dashboard/app/portfolio/page.tsx` — 포트폴리오 (paper trading 원장)
- `test/impl/34/scenario.md`, `test/impl/34/result.md`

### 수정 파일
- `services/ingest/app/main.py` — esg, intraday 라우터 등록
- `services/analysis/app/main.py` — intraday_indicators 라우터 등록
- `services/analysis/app/schemas/screener.py` — min_esg_score, esg_score 필드
- `services/analysis/app/services/screener.py` — ESG 점수 조회+필터
- `services/rag/app/api/rag.py` — POST/GET /rag/ir-report
- `web/apps/bff/src/proxy/proxy.controller.ts` — portfolio, rag/ir-report, esg, intraday, screener, agents, backtest 라우트
- `web/apps/dashboard/app/page.tsx` — D-5 ESG 패널, esg 서버 사이드 fetch
