# test/impl/9 — 차수 9 고도화 시험 결과

**판정: PASS (186/186)**
**일시: 2026-06-07**

## 총괄

| 영역 | 서비스 | 러너 | 결과 |
|------|--------|------|------|
| 다지표·FinBERT + PER/n-step/noisy DQN + 기존 | analysis | pytest | ✅ 60 |
| 종목 동적 구독 + 기존 | ingest | pytest | ✅ 59 |
| pgvector + 인메모리 | rag | pytest | ✅ 10 |
| 알림 + 멀티에이전트 | agents | pytest | ✅ 9 |
| 리스크 + 베타·정보비율·트래킹에러 | risk-engine | cargo | ✅ 31 |
| TUI | apps/tui | cargo | ✅ 9 |
| Web | web | vitest | ✅ 8 |
| **합계** | | | **✅ 186 passed, 0 failed** |

## 실행 로그

```
ingest    : 59 passed (+ 동적 구독)
analysis  : 60 passed (+ 다지표·FinBERT mock·실모델 + PER/n-step/noisy DQN)
rag       : 10 passed
agents    :  9 passed
risk-engine: 31 passed (+ beta·IR·TE)
tui        :  9 passed
web        :  8 passed
```

## 구현 요약

| 기능 | 구현 |
|------|------|
| 다지표 macro | `MACRO_INDICES`(콤마) 지수·환율·금리 z-score 합성, 일부 실패 시 가능 심볼만 평균 |
| FinBERT 센티먼트 | transformers 5.10 설치, `ProsusAI/finbert` 지연 로드, finbert_enabled 시 우선·실패 시 키워드 폴백. 실모델 추론 검증(긍정>부정) |
| PER·n-step·noisy DQN | `NoisyLinear`(factorized gaussian), n-step 리턴 누적, PER 우선순위 샘플링(|TD|^α)·우선순위 갱신, Double DQN, 시드 결정적 |
| 종목 동적 구독 | `MultiplexRouter.subscribe/unsubscribe/is_subscribed`, `build_sub_message`·`build_unsub_message`(tr_type 1/2) |
| 위험조정 성과 | `risk_metrics` → beta(cov/var), 정보비율(active mean/TE), 트래킹에러(std active), `POST /paper/risk_metrics` |

## 통합 검증 (실 모델)

- transformers 5.10.2 설치, FinBERT 모델 로드 + 실추론(긍정 텍스트 > 부정 텍스트) 통과.

## 픽스 이력

- 없음(신규 추가, 기존 회귀 전부 통과).

## MVP 범위 한계 (다음 차수 후보)

- 다지표: z-score 단순 평균 — 가중·PCA·lead-lag 미적용.
- FinBERT: 영문 금융 모델 — 한국어 KR-FinBERT·종목별 텍스트 정렬 미적용.
- DQN: Rainbow 일부(Double·Dueling·PER·n-step·Noisy) — distributional(C51)·multi-step 튜닝 미적용.
- 동적 구독: 라우터 레벨 — 실 WS 런타임 구독/해지 송신 통합 미적용.
- 위험지표: beta·IR·TE — 롤링 윈도우·다요인(Fama-French) 미적용.
