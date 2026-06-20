# test/impl/11 — 차수 11 고도화 시험 시나리오

**범위**: 동적 가중·증분 PCA · QR-DQN/IQN · 실 WS 송신 통합·ack · 롤링 베타·5요인·Newey-West
**차수**: 11
**러너**: pytest(Python) · cargo test(Rust)

## 동적 가중·증분 PCA (services/analysis)

| TC | 시나리오 | 기대 |
|----|----------|------|
| DW-01 | dynamic 합성 | 변동성 역가중, finite |
| DW-02 | ipca 합성 | 롤링 PCA z-score |
| DW-03 | 변동성 역가중 우선순위 | 안정 지표 비중↑ |

## QR-DQN/IQN (services/analysis)

| TC | 시나리오 | 기대 |
|----|----------|------|
| QR-01 | QR-DQN 구조 | strategy=qrdqn, n_quantiles=8 |
| QR-02 | IQN 구조 | strategy=iqn |
| QR-03 | 시드 결정성 | 동일 final_equity |
| QR-04 | 데이터 부족 | ValueError |
| QR-05 | strategies 에 qrdqn·iqn | True |

## 실 WS 송신 통합·ack (services/ingest)

| TC | 시나리오 | 기대 |
|----|----------|------|
| AK-01 | generic ack | pending→acked, pending_acks 갱신 |
| AK-02 | kis ack | tr_key 인식 |
| AK-03 | 미지 ack 무시 | 변동 없음 |

## 롤링 베타·5요인·Newey-West (core/risk-engine)

| TC | 시나리오 | 기대 |
|----|----------|------|
| NW-01 | 5요인 + NW SE | alpha+5betas+6 SE, finite |
| NW-02 | lag=0 ↔ plain OLS | 계수 동일 |
| (회귀) | 롤링·기존 factor | 통과 |

## 금융 규제 케이스 (COMPLIANCE.md)

- **시변 합성**: 동적 가중·증분 PCA → 거시 구조 변화 추적, 가중치 산출 근거 명시.
- **HAC 추론**: Newey-West 표준오차 → 자기상관·이분산 보정 유의성 검정(엄밀 통계).
- **세션 신뢰성**: 구독 ack 추적 → 미확인 구독 감지(재송신 트리거 기반).
- **RL 재현성**: QR-DQN/IQN 분위수 학습 시드 고정 → 동일 결과(감사).
