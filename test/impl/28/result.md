# iter-28 결과

## 판정: PASS

## 시험 실행 요약

### T1. TypeScript 컴파일
```
npx tsc --noEmit
# 출력 없음 (0 errors)
```
결과: ✅ PASS

### T2+T3. vitest 전체
```
Test Files  3 passed (3)
     Tests  50 passed (50)
  Start at  15:22:27
  Duration  244ms
```
결과: ✅ PASS (50/50)

| 파일 | 케이스 수 | 결과 |
|---|---|---|
| lib/candles.spec.ts | 5 | ✅ |
| lib/format.spec.ts | 6 | ✅ |
| lib/tooltips.spec.ts | **39** | ✅ |

## 구현 완료 항목

### 신규 파일
| 파일 | 내용 |
|---|---|
| `components/Tooltip.tsx` | `'use client'` 범용 툴팁 컴포넌트. position:fixed, delay 260ms, block prop, 뷰포트 flip |
| `lib/tooltips.ts` | 40개 항목 한국어 툴팁 콘텐츠 사전 (`as const`) |
| `lib/tooltips.spec.ts` | 39개 내용 검증 테스트 |

### 수정 파일
| 파일 | 변경 내용 |
|---|---|
| `components/Sidebar.tsx` | 메뉴 6개 + 페르소나 4개 + PERSONA 헤더 + 서비스 상태 4개 → 총 15개 항목에 Tooltip 적용 |
| `app/page.tsx` | MetricCard 5개 + Panel 7개 + IndRow 6개 + RiskRow 3개 + 수급 행 3개 + KOSPI/페르소나 배지 2개 → 총 26개 항목 |

**전체 툴팁 적용 항목: 40개**

## 툴팁 세부 내용 커버리지

| 카테고리 | 항목 | 특징 |
|---|---|---|
| 페르소나 | 스캘퍼/데이/스윙/포지션 | (전략)·(특징)·(파라미터) 3섹션 |
| 메뉴 | 대시보드~에이전트 | 화면 역할 + 주요 기능 |
| 서비스 상태 | ingest/analysis/agents/risk | 포트·기술스택·핵심 기능 |
| 지표 | RSI/MACD/Signal/ATR/EMA/SMA/Bollinger | 계산식·해석·활용법 |
| 시그널/결정 | 지표시그널/에이전트결정 | BUY/SELL/HOLD 정의 + 에이전트 역할 |
| 리스크 | Stop-Loss/일일한도/포지션한도 | 동작방식·페르소나별 기본값 |
| 패널 | 7개 | Phase 상태·데이터 출처 포함 |
| 수급 | 기관/외국인/개인 | 해석법·KRX 출처 안내 |
| 배지 | KOSPI/페르소나 | 지수 정의·페르소나 개요 |

## 전체 테스트 현황 (iter-28 기준)

| 서비스 | 도구 | 케이스 수 |
|---|---|---|
| web/dashboard | vitest | 50 |
| services/ingest | pytest | 305 |
| services/analysis | pytest | — |
| risk-engine | cargo test | 81 |
| web (mpm) | vitest | 17 |
| **합계** | | **453** |

> Python 305 + Rust 81 + Web 50 + mpm 17 = **453**
