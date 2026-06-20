# test/impl/3 — 고도화 기능 시험 시나리오

**범위**: F2.2 LSTM · F3.2 pgvector 영속화 · F1.2 브로커 WS · F5 백테스팅 · F6.3 알림 · 가상(시뮬레이션) 체결
**차수**: 3
**러너**: pytest(Python) · cargo test(Rust) · vitest(Web)

## F2.2 LSTM 실모델 (services/analysis, PyTorch)

| TC | 시나리오 | 기대 |
|----|----------|------|
| LSTM-01 | `predict_lstm` 구조 | model=lstm-v1, 4 horizon, direction/confidence/price |
| LSTM-02 | 동일 시드 재현성 | 두 호출 동일 예측 (감사 가능) |
| LSTM-03 | linear 모델 라벨 유지 | linear-regression-v1 |

> 비고: torch 학습은 메인 스레드 직접 호출로 시험(FastAPI 워커스레드+OpenMP segfault 회피). HTTP `/predict?model=lstm` 는 async 엔드포인트로 메인 이벤트루프 실행.

## F3.2 pgvector 영속화 (services/rag)

| TC | 시나리오 | 기대 |
|----|----------|------|
| PG-01 | add + count | 2건 |
| PG-02 | 동일 id upsert | count=1 |
| PG-03 | 검색 랭킹 | Fed 질의 → fed 문서 최상위 |
| PG-04 | 인스턴스 간 영속 | 새 연결에서 데이터 조회 |
| (인메모리 회귀) | 기존 6 케이스 | 변동 없음 |

> 실 postgres 필요(`make up`). 미연결 시 자동 skip. DATABASE_URL=postgres 면 pgvector, 아니면 인메모리 폴백.

## F1.2 브로커 WS 실연동 (services/ingest)

| TC | 시나리오 | 기대 |
|----|----------|------|
| BF-01 | `simulate_tick` 변동폭 | ±0.3% 이내 |
| BF-02 | 동일 시드 결정성 | 동일 가격 |
| BF-03 | WS `/market/feed/{ticker}` | source=simulated 틱 수신 |

> BROKER_WS_URL 설정 시 실 브로커 WebSocket 연결, 미설정 시 random-walk 시뮬레이션.

## F5 백테스팅 (services/analysis)

| TC | 시나리오 | 기대 |
|----|----------|------|
| BT-01 | 상승추세 백테스트 | final_equity>0, MDD∈[-100,0], 승률∈[0,1] |
| BT-02 | 데이터 부족 | ValueError |
| BT-03 | 수수료 영향 | 고수수료 ≤ 무수수료 최종자산 |
| BT-04 | 지표 키 존재 | sharpe·sortino·win_rate·profit_factor·MDD |
| BT-05 | `/backtest/` API | ticker·sharpe·bars 반환 |

## F6.3 알림 (services/agents)

| TC | 시나리오 | 기대 |
|----|----------|------|
| NT-01 | 미설정 no-op | telegram/discord false, 200 |
| NT-02 | 메시지 포맷 | event·payload 포함 |
| NT-03 | Discord 성공(mock) | discord true |

## 가상 체결 paper-trading (core/risk-engine, Rust)

| TC | 시나리오 | 기대 |
|----|----------|------|
| PT-01 | 매수 + 슬리피지 | 체결가 > 기준가, 포지션 생성 |
| PT-02 | 매도 실현손익 | 상승매도 → realized_pnl>0 |
| PT-03 | 초과매도 거부 | rejected, 포지션 불변 |
| PT-04 | 0수량 거부 | rejected |
| PT-05 | 복수매수 평균단가 | 평균 산출 |
| PT-06 | 미실현 P&L | mark 상승 → 양수 |
| PT-07 | **원장 append-only** | 모든 체결 보존(감사) |

## 금융 규제 케이스 (COMPLIANCE.md)

- **실거래 미체결**: 모든 주문은 가상(시뮬레이션) 체결 — 실제 브로커 송출 없음. `source=simulated`.
- **거래기록 보존**: paper 원장 append-only(PT-07) — 전자금융거래법 §22 정신.
- **재현성**: LSTM 시드 고정(LSTM-02) — 모델 판정 감사 가능.
- **시크릿 분리**: 알림 토큰·브로커 URL 모두 env(Keychain/Vault), 코드/파일 미보관.
- **부분 장애 격리**: pgvector 연결 실패 → 인메모리 폴백, 알림 미설정 → no-op.
