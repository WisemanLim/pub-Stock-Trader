# test/impl/2 — F1.2~F6.2 전 기능 구현 시험 시나리오

**범위**: PRD F1.2, F1.3, F2, F3.1, F3.2, F4, F6.1, F6.2  
**차수**: 2  
**러너**: pytest(Python) · cargo test(Rust) · vitest(Web)  
**의존 격리**: FinanceDataReader·feedparser·httpx → mock / 외부 서비스 비호출

## F1.2 호가창 (services/ingest)

| TC | 시나리오 | 기대 |
|----|----------|------|
| OB-01 | `GET /orderbook/005930` | 10레벨 호가, spread>0, mid>0 |
| OB-02 | `?levels=20` | 20레벨 |
| OB-03 | ask 가격 오름차순 | 정렬 검증 |
| OB-04 | bid 가격 내림차순 | 정렬 검증 |
| OB-05 | 데이터 없음 | 404 |

## F1.3 뉴스 RSS (services/ingest)

| TC | 시나리오 | 기대 |
|----|----------|------|
| NW-01 | `GET /news/sources` | 소스 목록 |
| NW-02 | `GET /news/reuters-business` (mock) | count=2, 항목 파싱 |
| NW-03 | 미지원 소스 | 404 |
| NW-04 | `?limit=5` | count ≤ 5 |

## F2 기술지표·예측·스크리너 (services/analysis)

| TC | 시나리오 | 기대 |
|----|----------|------|
| AN-01 | `/indicators/005930` | RSI 0~100, MACD, Bollinger upper>lower, signal |
| AN-02 | 데이터 없음 | 404 |
| AN-03 | `/predict/005930` | 4개 horizon, direction, confidence 0~1 |
| AN-04 | `/screener` POST RSI 필터 | matched≥1, signal 분류 |

## F3.2 Quant RAG (services/rag)

| TC | 시나리오 | 기대 |
|----|----------|------|
| RAG-01 | `/rag/ingest` 문서 3개 | ingested=3 |
| RAG-02 | `/rag/query` Fed 질의 | 최상위 근거=Fed 문서, grounded=true |
| RAG-03 | 빈 스토어 질의 | **환각차단**: sources=[], grounded=false |
| RAG-04 | `/rag/eval` | groundedness>0.5 |

## F3.1 멀티에이전트 (services/agents)

| TC | 시나리오 | 기대 |
|----|----------|------|
| AG-01 | `/agents/personas` | scalper<position 비중 상한 |
| AG-02 | `/agents/analyze` (RSI25, UP) | 4-에이전트 노트, BUY, confidence 0.8 |
| AG-03 | persona별 비중 | scalper < swing |
| AG-04 | 미지원 persona | 400 |
| AG-05 | **외부 서비스 장애** | 200 + degrade 노트 + HOLD |

## F4 리스크 엔진 (core/risk-engine, Rust)

| TC | 시나리오 | 기대 |
|----|----------|------|
| RK-01 | 전 규칙 통과 | Hold |
| RK-02 | Stop-Loss -2% 도달 | ForceSell |
| RK-03 | Trailing Stop (최고가 -5%) | ForceSell |
| RK-04 | 진입가 미만 트레일링 무시 | 미발동 |
| RK-05 | Take-Profit +10% | TakeProfit |
| RK-06 | 일일손실 -5% | ForceSell + block |
| RK-07 | 브로커 단절 Fail-Safe | BlockBuy |
| RK-08 | 포지션 한도 초과 | ReducePosition |
| RK-09 | **우선순위**: 손절 > 사이징 | ForceSell |

## F6.1 스캘퍼 TUI (apps/tui, Rust)

| TC | 시나리오 | 기대 |
|----|----------|------|
| TUI-01 | spread/mid 계산 | best ask-bid |
| TUI-02 | [b] 매수 | 포지션+1, 평균단가 |
| TUI-03 | 2회 매수 평균단가 | 평균 산출 |
| TUI-04 | [s] 매도 전량청산 | 진입가 리셋 |
| TUI-05 | 미실현 P&L | (현재가-진입가)*수량 |
| TUI-06 | [q] 종료 플래그 | should_quit |

## F6.2 Web 대시보드 (web, TS)

| TC | 시나리오 | 기대 |
|----|----------|------|
| BFF-01 | serviceUrl 빌드 | 슬래시 정규화 |
| BFF-02 | 5개 백엔드 서비스 매핑 | agents/analysis/ingest/rag/risk |
| DASH-01 | formatPrice 천단위 | "73,500" |
| DASH-02 | formatPct 부호 | "+2.10%" / "-1.50%" |
| DASH-03 | signalColor | BUY=green, SELL=red |

## 금융 규제 케이스 (COMPLIANCE.md)

- **F4 감사 로그**: RiskDecision.triggered 규칙 식별자 배열 — 모든 청산 판정 추적 가능 (전자금융거래법 §22).
- **F4 감정배제 강제**: Stop-Loss/일일한도가 사람·AI 판단보다 우선(우선순위 테스트 RK-09).
- **F3.2 환각차단**: 근거 없으면 답변 거부(RAG-03) — 허위 투자정보 생성 방지.
- **부분 장애 격리**: 에이전트 degrade(AG-05)·Redis 미설정(impl/1 TC-08) → 핵심 조회 비차단.
