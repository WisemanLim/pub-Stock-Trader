# test/impl/9 — 차수 9 고도화 시험 시나리오

**범위**: 다지표·FinBERT 센티먼트 · PER·n-step·noisy DQN · 종목 동적 구독 · 베타·정보비율·트래킹에러
**차수**: 9
**러너**: pytest(Python) · cargo test(Rust)

## 다지표·FinBERT 센티먼트 (services/analysis)

| TC | 시나리오 | 기대 |
|----|----------|------|
| MC-01 | 다지표 합성 z-score | 평균~0, 단조증가 |
| MC-02 | 짧은 시계열 패딩 | length 유지 |
| MC-03 | 전 심볼 실패 폴백 | 중립 0 |
| FB-01 | FinBERT 활성 추론(mock) | positive>0.5 |
| FB-02 | FinBERT 불가 → 키워드 폴백 | 키워드 점수 |
| FB-03 | **FinBERT 실모델**(미설치 skip) | 긍정>부정 |

## PER·n-step·noisy DQN (services/analysis)

| TC | 시나리오 | 기대 |
|----|----------|------|
| ND-01 | NoisyLinear 동작 | forward 정상, 학습 시 노이즈 |
| ND-02 | n-step 리턴 | n_step 파라미터 반영 |
| ND-03 | PER 우선순위 샘플링 | TD-error 가중 샘플 |
| ND-04 | 시드 결정성 | 동일 final_equity |

## 종목 동적 구독 (services/ingest)

| TC | 시나리오 | 기대 |
|----|----------|------|
| DS-01 | subscribe 신규/중복 | True/False |
| DS-02 | unsubscribe | 제거 후 미라우팅 |
| DS-03 | is_subscribed | 상태 조회 |
| DS-04 | sub/unsub 메시지 generic·kis | tr_type 1/2 |

## 베타·정보비율·트래킹에러 (core/risk-engine)

| TC | 시나리오 | 기대 |
|----|----------|------|
| RM-01 | beta·IR·TE 산출 | finite, TE≥0 |
| RM-02 | 길이 불일치 | (0,0,0) |

## 금융 규제 케이스 (COMPLIANCE.md)

- **센티먼트 설명가능성**: FinBERT(라벨·스코어) + 키워드 폴백 — 점수 산출 근거 추적.
- **위험조정 성과**: beta·정보비율·트래킹에러 → 벤치마크 대비 위험·일관성 보고.
- **RL 재현성**: noisy/PER DQN 시드 고정 → 동일 결과(감사).
- **외부 의존 격리**: 다지표 일부 실패 시 가능 심볼만 합성, FinBERT 불가 시 키워드 폴백.
