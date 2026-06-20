# test/impl/7 — 차수 7 고도화 시험 시나리오

**범위**: MACD·거시·뉴스 채널 · DQN 리플레이 버퍼·타깃 네트워크 · 하트비트 핑퐁 · 손익곡선 DB 영속화·기간 집계
**차수**: 7
**러너**: pytest(Python) · cargo test(Rust)

## MACD·거시·뉴스 채널 (services/analysis)

| TC | 시나리오 | 기대 |
|----|----------|------|
| CH-01 | 6채널 피처 노출 | [close,volume,rsi,macd_hist,macro,news] |
| CH-02 | 6채널 체크포인트 | n_features=6, features 보존 |
| CH-03 | provider 주입 | macro·news 콜백 호출됨 |
| CH-04 | provider 길이 불일치 | 중립 폴백, 정상 예측 |

## DQN 리플레이 버퍼·타깃 네트워크 (services/analysis)

| TC | 시나리오 | 기대 |
|----|----------|------|
| DQ-01 | 리플레이 파라미터 | buffer_size·batch_size·target_sync 동작 |
| DQ-02 | 시드 결정성(리플레이) | 동일 final_equity |

## 하트비트 핑퐁 (services/ingest)

| TC | 시나리오 | 기대 |
|----|----------|------|
| HB-01 | ping generic/kis | 포맷별 메시지 |
| HB-02 | pong 인식 | generic/kis True |
| HB-03 | interval 후 ping | should_ping True, mark 후 False |
| HB-04 | timeout stale | True |
| HB-05 | 활동 시 stale 해제 | False |

## 손익곡선 DB 영속화·기간 집계 (core/risk-engine)

| TC | 시나리오 | 기대 |
|----|----------|------|
| EQ-01 | mark ts 누적 | equity_curve 점 |
| EQ-02 | daily 집계 | 버킷별 OHLC, points |
| EQ-03 | 빈 곡선 집계 | [] |
| (통합) | paper_equity 영속·하이드레이션 | DB 행·재시작 복원 |

## 금융 규제 케이스 (COMPLIANCE.md)

- **모델 재현성**: DQN 리플레이 샘플링 시드 고정 → 동일 결과(감사).
- **손익 영속·집계**: paper_equity 영속 + 일/주 OHLC 집계 → 기간별 평가손익 보고.
- **세션 안정성**: 하트비트 ping + stale 감지 → 좀비 연결 차단(재연결 트리거).
- **외부 채널 격리**: 거시·뉴스 provider 미설정/오류 시 중립 폴백 — 부분 장애 격리.
