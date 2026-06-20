# test/impl/26 — 차수 26 시험 결과 (Phase 0 UI + 기능 수정)

**판정: PASS (412/412 + TS clean)**
**일시: 2026-06-18**

## 총괄

| 영역 | 러너 | 결과 |
|------|------|------|
| web (dashboard 22 + bff 10) | vitest | ✅ 32 |
| analysis | pytest | ✅ 131 |
| ingest | pytest | ✅ 105 |
| rag | pytest | ✅ 10 |
| agents | pytest | ✅ 36 |
| risk-engine | cargo | ✅ 72 |
| tui | cargo | ✅ 9 |
| tools/mpm | pytest(standalone) | ✅ 17 |
| **합계** | | **✅ 412 passed, 0 failed** |
| TypeScript (`tsc --noEmit`) | tsc | ✅ exit 0 (오류 0) |

차수25 406 → 차수26 412 (+6: `findCandleIndex` 툴팁 좌표 조회).

## 수정/구현 요약

| 항목 | 파일 | 내용 |
|------|------|------|
| **테마 토글** | `components/ThemeProvider.tsx` (신규) | `'use client'` Context — dark/light 전환. `localStorage('st-theme')` 영속. `document.documentElement.setAttribute('data-theme', …)` |
| **라이트 테마** | `app/globals.css` | `[data-theme="light"]` 블록 — 13개 CSS 변수 오버라이드. 다크↔라이트 전환 시 전 컴포넌트 자동 반영 (CSS var 참조) |
| **테마 버튼** | `components/TopBar.tsx` | `useTheme()` 연동. 다크: ☀, 라이트: ◑ 토글 버튼. `title` 속성으로 접근성 제공 |
| **시계 틱** | `components/TopBar.tsx` | `ClockDisplay` — `useEffect + setInterval(1000)` 로 1초 갱신. 기존: 서버 렌더 고정값 |
| **캔들 툴팁** | `components/CandleChart.tsx` | `onMouseMove` — SVG 스케일 보정(display px → SVG 좌표계) → `findCandleIndex` → `CandleTooltip` 절대 위치 렌더. 우측 경계 자동 flip. OHLCV + 등락률 표시 |
| **findCandleIndex** | `lib/candles.ts` | X 픽셀 → 캔들 인덱스 순수 함수. 범위 클램프. 빈 배열/-0 width → -1 |
| **findCandleIndex 시험** | `lib/candles.spec.ts` | +6 케이스: 좌끝·우끝·중간·빈 배열·0폭·범위 초과 |
| **TS 오류 수정** | `app/page.tsx` | `rsiColor(rsi?: number \| null)` — 기존 `null` 전달 TS2345 2건 해소 |
| **서브 페이지 404 수정** | `app/{portfolio,strategy,risk,backtest,agents}/page.tsx` | 각 라우트 `ComingSoon` 플레이스홀더 — 구현 예정 기능 목록 + PRD 링크 |
| **layout ThemeProvider** | `app/layout.tsx` | `<html suppressHydrationWarning>` + `<ThemeProvider>` 래핑 |

## 기능 시험 (수동)

| 시나리오 | 결과 |
|---------|------|
| 테마 토글 버튼 클릭 (다크→라이트) | ✅ 전 컴포넌트 배경·텍스트·캔들 색 일괄 전환 |
| 새로고침 후 테마 유지 | ✅ localStorage 영속 |
| 캔들 차트 마우스오버 | ✅ 날짜·O·H·L·C·거래량·등락률 툴팁 표시 |
| 툴팁 우측 경계 flip | ✅ SVG 오른쪽 50% 이상에서 툴팁 좌측으로 반전 |
| 시계 1초 갱신 | ✅ 실시간 틱 |
| 포트폴리오/전략/리스크/백테스팅/에이전트 메뉴 클릭 | ✅ 404 → 플레이스홀더 페이지 정상 렌더 |
| TypeScript 타입 체크 | ✅ `tsc --noEmit` exit 0 |

## 시험 실행 로그

```
web/apps/dashboard vitest run
  ✓ lib/candles.spec.ts (17 tests) 3ms
  ✓ lib/format.spec.ts  (5 tests) 10ms
  Tests 22 passed (22)

web/apps/bff vitest run
  ✓ src/config.spec.ts           (3 tests)
  ✓ src/proxy/candles.spec.ts    (4 tests)
  ✓ src/ticker.util.spec.ts      (3 tests)
  Tests 10 passed (10)

tsc --noEmit → exit 0 (errors: 0)
```
