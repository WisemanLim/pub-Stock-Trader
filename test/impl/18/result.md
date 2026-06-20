# test/impl/18 — 차수 18 고도화 시험 결과

**판정: PASS (279/279)**
**일시: 2026-06-07**

## 총괄

| 영역 | 서비스 | 러너 | 결과 |
|------|--------|------|------|
| QuEST 비선형축소·병렬 롤아웃 + 기존 | analysis | pytest | ✅ 112 |
| 토큰버킷 처리율 + 기존 | ingest | pytest | ✅ 81 |
| pgvector + 인메모리 | rag | pytest | ✅ 10 |
| 알림 + 멀티에이전트 | agents | pytest | ✅ 9 |
| 리스크 + companion 고유값 사영 | risk-engine | cargo | ✅ 50 |
| TUI | apps/tui | cargo | ✅ 9 |
| Web | web | vitest | ✅ 8 |
| **합계** | | | **✅ 279 passed, 0 failed** |

## 실행 로그

```
ingest    : 81 passed (+ 토큰버킷 처리율)
analysis  : 112 passed (+ QuEST 해석적 비선형축소 + 스레드풀 병렬 롤아웃)
rag       : 10 passed
agents    :  9 passed
risk-engine: 50 passed (+ companion 고유값 반경 안정성 사영)
tui        :  9 passed
web        :  8 passed
```

## 구현 요약

| 기능 | 구현 |
|------|------|
| QuEST 비선형축소 | `_quest_shrink`(Ledoit-Wolf 2020 해석적: Epanechnikov 커널 밀도 f̃·Hilbert Hf̃ → d̃_i 역변환), `MACRO_COMBINE=erc_quest`. p≥n 폴백 |
| 멀티 병렬 롤아웃 | dpg `parallel`(ThreadPoolExecutor), 롤아웃별 시드 generator+순서보존 → 순차=병렬 동일(결정적) |
| 토큰버킷 처리율 | `_tb_consume`/`_tb_refill`(rate·capacity), `add` 신규 구독만 토큰 소비, `tokens_available` |
| companion 고유값 사영 | `build_companion`(cols·p companion)·`companion_radius`(power iter, p>1 정확), `factor_regression_qs_var_full(companion)` |

## 픽스 이력

- 없음(신규 추가, 기존 회귀 전부 통과).

## 거시 합성 모드 (총 14종)
mean·weighted·dynamic·riskparity·erc·erc_newton·erc_lw·erc_cc·erc_oas·erc_nlw·erc_quest·pca·ipca·ccipca

## MVP 범위 한계 (다음 차수 후보)

- QuEST: 단일 커널 밀도 추정 — 격자 QuEST 수치역전·MP 적합도 검정 미적용.
- 병렬: 스레드풀(GIL) — 실제 멀티프로세스(모델 복제·gather) 미적용.
- 토큰버킷: 전역 단일 버킷 — 채널별·우선순위 큐 미적용.
- companion: 반경 스케일 사영 — 개별 고유값 복소수 클리핑(Schur) 미적용.
