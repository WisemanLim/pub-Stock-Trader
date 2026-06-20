# iter-28 시나리오: 대시보드 전체 툴팁 시스템

## 구현 목표
대시보드 UI 전 항목에 마우스오버 툴팁을 제공한다.
상세한 한국어 설명으로 금융 도메인 전문 지식을 인라인 제공.

## 대상 항목

| 카테고리 | 항목 | 개수 |
|---|---|---|
| 페르소나 | 스캘퍼/데이/스윙/포지션 | 4 |
| 메뉴 | 대시보드/포트폴리오/전략/리스크/백테스팅/에이전트 | 6 |
| 서비스 상태 | ingest/analysis/agents/risk | 4 |
| 지표 MetricCard | 현재가/RSI(14)/Bollinger/지표시그널/에이전트결정 | 5 |
| 기술지표 행 | RSI/MACD/Signal/ATR/EMA(20)/SMA(20) | 6 |
| 패널 제목 | 캔들차트/기술지표/수급동향/리스크상태/시장경보/공매도/포지션요약 | 7 |
| 리스크 행 | Stop-Loss/일일한도/포지션한도 | 3 |
| 수급 행 | 기관/외국인/개인 | 3 |
| 배지 | KOSPI/페르소나 | 2 |

**합계: 40개 항목**

## 생성/수정 파일
- `web/apps/dashboard/components/Tooltip.tsx` (신규)
- `web/apps/dashboard/lib/tooltips.ts` (신규)
- `web/apps/dashboard/lib/tooltips.spec.ts` (신규)
- `web/apps/dashboard/components/Sidebar.tsx` (수정)
- `web/apps/dashboard/app/page.tsx` (수정)

## Tooltip 컴포넌트 사양
- `'use client'` — position:fixed + viewport 좌표 (CandleChart 툴팁과 동일 방식)
- 260ms delay (마우스 일시 통과 시 팝업 방지)
- 오른쪽 경계 flip (window.innerWidth 기준)
- `block` prop — div 래퍼 (Link 등 블록 요소 감쌀 때)
- `title` prop — 굵은 헤더, `content` — `\n` 줄바꿈 본문

## 시험 항목

### T1. TypeScript 컴파일
- `npx tsc --noEmit` → 오류 없음

### T2. vitest — tooltips.spec.ts 신규 28개 케이스
- 페르소나 4개 내용 검증
- 메뉴 6개 존재 검증
- 지표 (rsi/macd/bollinger/signal/agentDecision) 핵심 문구 검증
- 리스크 (stopLoss/positionLimit) 핵심 문구 검증
- 패널 (candleChart/flow) 핵심 문구 검증
- 수급 행 (institution/foreign/individual) 검증
- 서비스 상태 4개 포트 언급 검증
- misc (kospi/persona) 검증

### T3. 기존 vitest 회귀 (22개)
- lib/candles.spec.ts 5개
- lib/format.spec.ts 6개
- lib/tooltips.spec.ts 이전 22개 → 이번에 신규 28개 추가

### T4. 총계
- Web vitest: 50개 이상 PASS
- TS: clean
