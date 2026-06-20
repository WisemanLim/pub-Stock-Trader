# test/impl/4 — 차수 4 고도화 시험 시나리오

**범위**: LSTM 사전학습 · 다전략 백테스팅 · 실 브로커 프로토콜 어댑터 · 가상체결 다종목·DB 영속화
**차수**: 4
**러너**: pytest(Python) · cargo test(Rust)

## LSTM 사전학습 (services/analysis)

| TC | 시나리오 | 기대 |
|----|----------|------|
| LS-01 | predict 구조 | model=lstm-v1, weights_source∈{checkpoint,on-the-fly} |
| LS-02 | train_and_save | 체크포인트(.pt) 생성, samples>0 |
| LS-03 | 체크포인트 로딩 | 학습 후 predict → weights_source=checkpoint |
| LS-04 | 체크포인트 부재 | weights_source=on-the-fly |
| LS-05 | `POST /predict/{t}/train` | async 엔드포인트, 체크포인트 메타 반환 |

## 다전략 백테스팅 (services/analysis)

| TC | 시나리오 | 기대 |
|----|----------|------|
| BT-01 | sma_cross | strategy 라벨, MDD∈[-100,0] |
| BT-02 | rsi_threshold | sharpe 산출 |
| BT-03 | macd_cross | num_trades≥0 |
| BT-04 | 미지원 전략 | ValueError |
| BT-05 | 수수료 영향 | 고수수료 ≤ 무수수료 |
| BT-06 | `/backtest/strategies` | 3개 전략 목록 |
| BT-07 | `/backtest/` API | strategy·params 반영 |

## 실 브로커 프로토콜 어댑터 (services/ingest)

| TC | 시나리오 | 기대 |
|----|----------|------|
| BA-01 | generic JSON | price 정규화 |
| BA-02 | generic 잘못된 JSON | None |
| BA-03 | generic price 누락 | None |
| BA-04 | kis 텍스트(^구분) | 종목·현재가·등락률 파싱 |
| BA-05 | kis JSON(stck_prpr) | price 파싱 |
| BA-06 | kis 필드부족 | None |
| BA-07 | 미지원 어댑터 | ValueError |
| BA-08 | 커스텀 어댑터 등록 | register → 동작 |

## 가상체결 다종목 + DB 영속화 (core/risk-engine)

| TC | 시나리오 | 기대 |
|----|----------|------|
| PT-01~07 | 기존 단종목 체결·원장 | 회귀 통과 |
| PT-08 | **다종목 격리** | 005930·000660 포지션 독립, open_positions=2 |
| PT-09 | **원장 리플레이 복원** | replay → 포지션 재구성 |
| (통합) | postgres 영속 | paper_fills append, 재시작 하이드레이션 |

## 금융 규제 케이스 (COMPLIANCE.md)

- **거래기록 영속·불변**: paper_fills append-only(bigserial·created_at), 재시작 하이드레이션 — 전자금융거래법 §22.
- **실거래 미체결 유지**: DB 영속화에도 `source=simulated`/가상 — 실주문 송출 없음.
- **모델 재현성**: LSTM 체크포인트에 정규화 파라미터(lo/hi) 보존 → 동일 스케일 예측(감사).
- **부분 장애 격리**: DATABASE_URL 연결 실패 → 인메모리 폴백 + 경고 로그.
- **시크릿 분리**: 브로커 어댑터는 키 미보관, 연결계층(env/Keychain)만 주입.
