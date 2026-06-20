# iter-29 시나리오: 툴팁 뷰포트 방어 + 기업명 검색 + 캔들 차트 개선

## 구현 목표

### A. 툴팁 하단 클리핑 방어
화면 하단 항목(ingest/risk 상태 도트, 포지션 요약 등) 마우스오버 시
툴팁이 뷰포트 아래로 잘리지 않도록 자동 위 방향 flip.

### B. 기업명/종목코드 통합 검색
종목코드(숫자 6자리)뿐 아니라 기업명으로 검색 가능.
입력 즉시 자동완성 드롭다운(최대 8건): 기업명 + 시장구분 + 코드 표시.

### C. 캔들 차트 개선
1. **X축** — 날짜 레이블(MM/DD) 하단 표시
2. **Y축** — 가격 레이블(nice interval) 우측 표시
3. **반응형 폭** — ResizeObserver로 패널 폭에 맞게 자동 조정
4. **스크롤 줌** — 마우스 휠 위 = 줌인(봉 수 감소), 아래 = 줌아웃(봉 수 증가)
   - 최소 10봉, 최대 전체 봉 수

## 생성/수정 파일

| 파일 | 변경 |
|---|---|
| `components/Tooltip.tsx` | 하단 클리핑 방어: `useRef` 높이 측정 → 위로 flip |
| `lib/stocks.ts` | 신규: KRX 주요 종목 300여 개 정적 목록 + `searchStocks()` |
| `lib/stocks.spec.ts` | 신규: 14개 테스트 |
| `components/TopBar.tsx` | 기업명 검색 autocomplete (화살표 키·Enter·Escape·blur 처리) |
| `lib/candles.ts` | `candleLayout` — optional `minPrice`/`maxPrice` 파라미터 추가 |
| `lib/candles.spec.ts` | candleLayout 신규 2개 테스트 |
| `components/CandleChart.tsx` | X/Y축 + 반응형(ResizeObserver) + 스크롤 줌 전면 재작성 |

## 시험 항목

### T1. TypeScript 컴파일
`npx tsc --noEmit` → 오류 없음

### T2. vitest
- candles.spec.ts: 기존 14개 + 신규 2개 = 16개
- stocks.spec.ts: 신규 14개
- tooltips.spec.ts: 28개 (회귀)
- format.spec.ts: 5개 (회귀)
- **합계 68개 이상 PASS**

### T3. 동작 확인 (수동)
- 화면 하단 항목 hover → 툴팁이 위로 표시됨
- "삼성" 입력 → 삼성전자/삼성SDI 등 자동완성
- "005930" 입력 → 자동완성 코드 매칭
- 화살표 키로 항목 탐색, Enter로 선택
- 캔들 차트: 좌우에 날짜/가격 축 표시, 패널 폭에 맞게 확장
- 마우스 휠 스크롤 → 봉 수 변화 (줌인/줌아웃)
