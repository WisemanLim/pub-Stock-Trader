# iter-29 결과

## 판정: PASS

## 시험 실행 요약

### T1. TypeScript 컴파일
```
npx tsc --noEmit
# 출력 없음 (0 errors)
```
결과: ✅ PASS

### T2. vitest 전체
```
Test Files  4 passed (4)
     Tests  68 passed (68)
  Start at  15:35:33
  Duration  210ms
```
결과: ✅ PASS (68/68)

| 파일 | 케이스 수 | 결과 |
|---|---|---|
| lib/candles.spec.ts | **16** | ✅ (+2 candleLayout minPrice/maxPrice) |
| lib/stocks.spec.ts | **14** | ✅ (신규) |
| lib/tooltips.spec.ts | 28 | ✅ |
| lib/format.spec.ts | 5 | ✅ |
| lib/candles.spec.ts (기존 findCandleIndex) | 6 | ✅ |

## 구현 완료 항목

### A. 툴팁 하단 클리핑 방어
- `Tooltip.tsx` — `tooltipRef` + `useEffect`로 실제 높이 측정
- `below = pos.y + 14 + h + PADDING > window.innerHeight` → 위로 flip
- 첫 렌더 fallback: h=200px 추정치 사용 (다음 프레임에서 정밀 보정)

### B. 기업명 통합 검색 (`TopBar.tsx`)
- `lib/stocks.ts` — KOSPI 100여 + KOSDAQ 60여 = 약 165개 종목 정적 목록
- `searchStocks(query, limit=8)`:
  - 숫자 query → ticker startsWith 매칭
  - 문자 query → name contains 매칭
- 드롭다운: 기업명 + 시장 배지(KOSPI 파란색/KOSDAQ 초록색) + 코드
- 키보드: ↑↓ 탐색, Enter 선택, Escape 닫기
- `onBlur` 150ms 지연으로 클릭 이벤트 선행 보장
- 입력창 placeholder: "종목코드 / 기업명"

### C. 캔들 차트 개선 (`CandleChart.tsx`)
- **X축**: MM/DD 형식 날짜 레이블, 최대 `chartW/60`개 균등 배치
- **Y축**: nice interval 가격 눈금 + 레이블 (`K`/`M`/천 단위 구분)
  - 간격 계산: 1·2·2.5·5·10 × 10^n 중 최적 선택
- **반응형**: `ResizeObserver` → `svgWidth` state → SVG width 동기화
- **스크롤 줌**: `onWheel` + `visibleCount` state (ZOOM_STEP=5봉)
  - 휠 위 → 줌인(봉 수-5), 휠 아래 → 줌아웃(봉 수+5)
  - 범위: 최소 10봉 ~ 최대 전체 봉 수
- **패딩**: 상하 6% 여백으로 캔들이 경계에 닿지 않음
- `candleLayout` — optional `minPrice`/`maxPrice` 파라미터로 패딩 범위 전달

## 전체 테스트 현황 (iter-29 기준)

| 서비스 | 도구 | 케이스 수 |
|---|---|---|
| web/dashboard | vitest | **68** |
| services/ingest | pytest | 305 |
| risk-engine | cargo test | 81 |
| web (mpm) | vitest | 17 |
| **합계** | | **471** |

> Python 305 + Rust 81 + Web 68 + mpm 17 = **471**
