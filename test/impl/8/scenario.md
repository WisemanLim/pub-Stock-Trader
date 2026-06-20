# test/impl/8 — 차수 8 고도화 시험 시나리오

**범위**: 실 거시·뉴스 파이프라인 · ε 감쇠·Double/Dueling DQN · 다종목 멀티플렉싱 · 손익곡선 월/분기 집계·벤치마크 알파
**차수**: 8
**러너**: pytest(Python) · cargo test(Rust)

## 실 거시·뉴스 파이프라인 (services/analysis)

| TC | 시나리오 | 기대 |
|----|----------|------|
| CN-01 | 센티먼트 점수 양/음/중립 | 부호 일치 |
| CN-02 | macro 길이 정렬 | length 일치, 최신값 |
| CN-03 | macro 짧을 때 패딩 | length 유지 |
| CN-04 | macro 오류 폴백 | 중립 0 |
| CN-05 | news 센티먼트 집계 | [-1,1] |
| CN-06 | news 실패 폴백 | 0 |
| CN-07 | news provider broadcast | length 상수 |
| CN-08 | register 등록 | provider 설정됨 |

## ε 감쇠·Double/Dueling DQN (services/analysis)

| TC | 시나리오 | 기대 |
|----|----------|------|
| DD-01 | Dueling 네트워크 구조 | value+advantage 결합 동작 |
| DD-02 | ε 감쇠 | 학습 진행 시 epsilon 감소 |
| DD-03 | Double DQN 타깃 | online argmax + target eval |
| DD-04 | 시드 결정성 | 동일 final_equity |

## 다종목 멀티플렉싱 (services/ingest)

| TC | 시나리오 | 기대 |
|----|----------|------|
| MX-01 | generic 구독 메시지 | auth+구독 N개 |
| MX-02 | kis 구독 메시지 | approval + body 반복 |
| MX-03 | 빈 목록 | [] |
| MX-04 | 라우터 dispatch/drain | 종목별 라우팅, 미구독 False |
| MX-05 | 대소문자 무시 | 정규화 |
| MX-06 | WS 다종목 시뮬 | 두 종목 틱 수신 |

## 손익곡선 월/분기·알파 (core/risk-engine)

| TC | 시나리오 | 기대 |
|----|----------|------|
| CA-01 | epoch→year/month | 알려진 날짜 일치 |
| CA-02 | 월/분기 달력 집계 | 버킷 분리 |
| CA-03 | 알파 vs 벤치마크 | port-bench=alpha |
| CA-04 | 데이터 부족 알파 | (0,0,0) |

## 금융 규제 케이스 (COMPLIANCE.md)

- **모델 재현성**: Double/Dueling DQN 시드 고정 → 동일 결과(감사).
- **성과 투명성**: 월/분기 OHLC + 벤치마크 대비 알파 → 기간 성과·초과수익 보고.
- **외부 의존 격리**: 거시(FDR)·뉴스(ingest) 실패 시 중립 폴백 — 예측 비차단.
- **센티먼트 추적성**: 키워드 기반 점수(설명가능) — 운영 시 모델 교체 지점 명시.
