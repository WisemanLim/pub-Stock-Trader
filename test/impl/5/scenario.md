# test/impl/5 — 차수 5 고도화 시험 시나리오

**범위**: LSTM 스케줄 재학습·Transformer · 강화학습 백테스팅 · 브로커 인증·재연결 · 종목별 실현손익 분리
**차수**: 5
**러너**: pytest(Python) · cargo test(Rust)

## LSTM 스케줄 재학습 + Transformer (services/analysis)

| TC | 시나리오 | 기대 |
|----|----------|------|
| TF-01 | Transformer 예측 구조 | model=transformer-v1, 4 horizon |
| TF-02 | 미지원 arch | ValueError |
| TF-03 | 체크포인트 부재 → needs_retrain | True |
| TF-04 | scheduled_retrain stale→학습 | retrained=True, 재호출 fresh |
| TF-05 | Transformer 체크포인트 왕복 | weights_source=checkpoint |

## 강화학습 백테스팅 (services/analysis)

| TC | 시나리오 | 기대 |
|----|----------|------|
| RL-01 | Q-learning 구조 | strategy=qlearn, MDD∈[-100,0], 승률∈[0,1] |
| RL-02 | 시드 고정 재현성 | 동일 final_equity |
| RL-03 | 데이터 부족 | ValueError |
| RL-04 | `/backtest/rl` API | qlearn, bars 반환 |
| RL-05 | strategies 에 qlearn 포함 | True |

## 브로커 인증·재연결 (services/ingest)

| TC | 시나리오 | 기대 |
|----|----------|------|
| AU-01 | generic 인증 메시지 | action=auth, api_key |
| AU-02 | kis 인증 메시지 | approval_key, H0STCNT0 |
| AU-03 | 지수 백오프 | 0.5·2^n |
| AU-04 | 백오프 상한 | cap=30 |
| AU-05 | 음수 attempt | base |
| AU-06 | 무한 재시도(-1) | True |
| AU-07 | 유한 재시도 경계 | attempt<max |

## 종목별 실현손익 분리 (core/risk-engine)

| TC | 시나리오 | 기대 |
|----|----------|------|
| RP-01 | 종목별 실현손익 | 005930>0, 000660<0, 미보유=0, 합=전체 |

## 금융 규제 케이스 (COMPLIANCE.md)

- **모델 재현성**: Transformer/LSTM 시드 고정 + RL 시드 고정 → 동일 결과(감사).
- **스케줄 재학습 추적**: 체크포인트 trained_at 보존, stale 판정 명시적.
- **종목별 손익 투명성**: realized_by_ticker 분리 → 종목 단위 정산 대사 가능.
- **재연결 무중단**: 브로커 세션 유실 시 지수 백오프 재연결(인증 재수행) — Fail-Safe 보완.
- **시크릿 분리**: 인증 키는 broker_auth 헬퍼에 전달만, env/Keychain 주입.
