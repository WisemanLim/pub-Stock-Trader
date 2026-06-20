# test/impl/6 — 차수 6 고도화 시험 시나리오

**범위**: 멀티변량 입력 · DQN · 토큰 만료 갱신 · 종목별 미실현 손익곡선
**차수**: 6
**러너**: pytest(Python) · cargo test(Rust)

## 멀티변량 입력 (services/analysis)

| TC | 시나리오 | 기대 |
|----|----------|------|
| MV-01 | predict 피처 노출 | features=[close,volume,rsi] |
| MV-02 | 멀티변량 체크포인트 | n_features=3, features 보존, 로딩 예측 |

## DQN 백테스팅 (services/analysis)

| TC | 시나리오 | 기대 |
|----|----------|------|
| DQN-01 | 구조 | strategy=dqn, MDD∈[-100,0], 승률∈[0,1] |
| DQN-02 | 시드 결정성 | 동일 final_equity |
| DQN-03 | 데이터 부족 | ValueError |
| DQN-04 | strategies 에 dqn 포함 | True |

## 토큰 만료 갱신 (services/ingest)

| TC | 시나리오 | 기대 |
|----|----------|------|
| TK-01 | 최초 발급 | issue_count=1 |
| TK-02 | 캐시 재사용 | 만료 전 동일 토큰, count 불변 |
| TK-03 | 만료 후 재발급 | 새 토큰, count=2 |
| TK-04 | skew 선제 재발급 | 만료 59초 전 재발급 |
| TK-05 | invalidate 강제 재발급 | 401 등 대응 |
| TK-06 | 초기 만료 상태 | is_expired True |

## 종목별 미실현 손익곡선 (core/risk-engine)

| TC | 시나리오 | 기대 |
|----|----------|------|
| MM-01 | 종목별 미실현 | 005930>0, 000660<0 |
| MM-02 | 손익곡선 누적 | mark 2회 → curve 2점, 가격↑→미실현↑ |
| MM-03 | 가격 없음/청산 무시 | 빈 미실현 맵 |

## 금융 규제 케이스 (COMPLIANCE.md)

- **모델 재현성**: DQN torch 시드 고정 → 동일 결과(감사).
- **손익 투명성**: 종목별 미실현 + mark-to-market 손익곡선 → 일중 평가손익 추적.
- **토큰 수명 관리**: 만료 skew 선제 재발급·invalidate(401) → 세션 끊김 최소화, 키 미보관.
- **멀티변량 추적**: 체크포인트에 feature 목록·n_features 보존(모델 입력 감사).
