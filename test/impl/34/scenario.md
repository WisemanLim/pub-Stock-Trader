# Test Scenario — iter-34 (Phase D)

## 목표
Phase D 구현 검증:
- D-1 ESG 지수 점수 API (ingest)
- D-2 한국IR협의회 AI 분석보고서 RAG 적재 (rag)
- D-3 분봉 데이터 수집 (ingest)
- D-4 분봉 기반 기술지표 (analysis)
- D-5 웹 대시보드 ESG 위젯 (page.tsx)
- D-6 ESG 필터 스크리너 (analysis)
- 메뉴 연결: 전략·에이전트·백테스팅·리스크·포트폴리오 서브페이지
- BFF: portfolio, rag/ir-report 라우트 추가

## 시나리오

### S-34-01: ingest ESG 점수 API
- `GET /esg/{ticker}` → ticker=005930
- 응답: `{ ticker, total, e_score, s_score, g_score }`
- total = e_score + s_score + g_score, 0~100 범위

### S-34-02: ingest ESG 캐시
- 같은 ticker 2회 연속 호출
- 두 번째 호출 응답시간 < 첫 번째 (6h 캐시)

### S-34-03: ingest 분봉 데이터 5m
- `GET /market/intraday/{ticker}?interval=5m`
- 응답: `{ ticker, interval, bars: [{datetime, open, high, low, close, volume}] }`
- bars 비어있지 않음

### S-34-04: ingest 분봉 데이터 1m
- `GET /market/intraday/{ticker}?interval=1m`
- 응답 형식 동일

### S-34-05: analysis 분봉 지표
- `GET /indicators/intraday/{ticker}?interval=5m`
- 응답: `{ ticker, interval, rsi, macd, vwap }`
- 최소 1개 이상 지표 값 존재 (None 허용)

### S-34-06: rag IR 보고서 적재
- `POST /rag/ir-report` ticker=005930, title="삼성전자 분석", content="투자의견 매수..."
- 응답: `{ status: "ok", doc_id, total }`

### S-34-07: rag IR 보고서 조회
- S-34-06 적재 후 `GET /rag/ir-report/005930`
- 응답: `{ available: true, answer, sources }`

### S-34-08: rag IR 보고서 미적재 종목
- `GET /rag/ir-report/999999`
- 응답: `{ available: false }`

### S-34-09: analysis ESG 스크리너 필터
- `POST /screener/` min_esg_score=60
- 결과 모든 종목 esg_score >= 60 (또는 null 허용)

### S-34-10: analysis ESG 스크리너 zero min
- `POST /screener/` min_esg_score=0
- 필터 없는 경우와 동일하게 동작 (전체 스캔)

### S-34-11: BFF ESG 라우트
- `GET /api/esg/005930` (BFF:3002)
- ingest 프록시 확인

### S-34-12: BFF portfolio 라우트
- `GET /api/portfolio?account=default` (BFF:3002)
- risk-engine 프록시 (서비스 미기동 시 5xx 허용)

### S-34-13: BFF rag/ir-report 라우트
- `GET /api/rag/ir-report/005930` (BFF:3002)
- rag 프록시 확인

### S-34-14: 전략 서브페이지 TypeScript 컴파일
- `web/apps/dashboard/app/strategy/page.tsx` — tsc --noEmit PASS

### S-34-15: 에이전트 서브페이지 TypeScript 컴파일
- `web/apps/dashboard/app/agents/page.tsx` — tsc --noEmit PASS

### S-34-16: 백테스팅 서브페이지 TypeScript 컴파일
- `web/apps/dashboard/app/backtest/page.tsx` — tsc --noEmit PASS

### S-34-17: 리스크 서브페이지 TypeScript 컴파일
- `web/apps/dashboard/app/risk/page.tsx` — tsc --noEmit PASS

### S-34-18: 포트폴리오 서브페이지 TypeScript 컴파일
- `web/apps/dashboard/app/portfolio/page.tsx` — tsc --noEmit PASS

### S-34-19: BFF TypeScript 컴파일
- `web/apps/bff` — tsc --noEmit PASS (portfolio, rag routes 포함)

### S-34-20: page.tsx ESG 위젯 포함 컴파일
- `web/apps/dashboard` — tsc --noEmit PASS (D-5 ESG 패널 포함)

## 기존 회귀

### S-34-R01: ingest 전체 테스트 회귀
- 기존 168개 테스트 PASS

### S-34-R02: analysis 전체 테스트 회귀
- 기존 테스트 PASS

### S-34-R03: agents 전체 테스트 회귀
- 기존 6-agent 파이프라인 테스트 PASS
