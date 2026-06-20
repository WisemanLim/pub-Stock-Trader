# test/impl/10 — 차수 10 고도화 시험 시나리오

**범위**: 가중/PCA 합성·KR-FinBERT · Distributional C51 DQN · 실 WS 런타임 구독 송신 · 롤링 윈도우·Fama-French 다요인
**차수**: 10
**러너**: pytest(Python) · cargo test(Rust)

## 가중/PCA 합성·KR-FinBERT (services/analysis)

| TC | 시나리오 | 기대 |
|----|----------|------|
| WC-01 | weighted 합성 | 가중 평균, finite |
| WC-02 | pca 합성 | 제1주성분 z-score(평균~0) |
| WC-03 | KR-FinBERT 한글 라벨 | "긍정" 인식 → +점수 |
| (회귀) | mean 합성·폴백 | 기존 통과 |

## Distributional C51 (services/analysis)

| TC | 시나리오 | 기대 |
|----|----------|------|
| C51-01 | 구조 | strategy=c51, n_atoms=21 |
| C51-02 | 시드 결정성 | 동일 final_equity |
| C51-03 | 데이터 부족 | ValueError |
| C51-04 | strategies 에 c51 | True |

## 실 WS 런타임 구독 송신 (services/ingest)

| TC | 시나리오 | 기대 |
|----|----------|------|
| RS-01 | add/중복 | True/False, 명령 큐 적재 |
| RS-02 | drain_commands | 구독 메시지 반환·비움 |
| RS-03 | remove | 해지 메시지·라우터 갱신 |
| RS-04 | kis 메시지 | tr_type 1 |

## 롤링·Fama-French (core/risk-engine)

| TC | 시나리오 | 기대 |
|----|----------|------|
| RF-01 | 롤링 윈도우 지표 | 윈도우별 (beta,ir,te) finite |
| RF-02 | 3요인 OLS | alpha + 3 betas |
| RF-03 | 길이 불일치 | None |

## 금융 규제 케이스 (COMPLIANCE.md)

- **합성 투명성**: 가중치·PCA 로딩 명시적 — 거시 합성 근거 추적.
- **다요인 귀속**: Fama-French alpha/beta 분해 → 수익 원천(시장·규모·가치) 귀속 보고.
- **롤링 모니터링**: 윈도우별 beta·IR·TE → 시변 위험 추적.
- **RL 재현성**: C51 분포 학습 시드 고정 → 동일 결과(감사).
- **KR 센티먼트**: KR-FinBERT 한글 라벨 대응 — 국내 뉴스 분석.
