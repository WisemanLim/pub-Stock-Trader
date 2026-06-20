# test/impl/13 — 차수 13 고도화 시험 결과

**판정: PASS (232/232)**
**일시: 2026-06-07**

## 총괄

| 영역 | 서비스 | 러너 | 결과 |
|------|--------|------|------|
| 공분산 ERC·상태의존 FQF + 기존 | analysis | pytest | ✅ 86 |
| 지수 백오프·서킷브레이커 + 기존 | ingest | pytest | ✅ 70 |
| pgvector + 인메모리 | rag | pytest | ✅ 10 |
| 알림 + 멀티에이전트 | agents | pytest | ✅ 9 |
| 리스크 + QS 커널·prewhitening | risk-engine | cargo | ✅ 40 |
| TUI | apps/tui | cargo | ✅ 9 |
| Web | web | vitest | ✅ 8 |
| **합계** | | | **✅ 232 passed, 0 failed** |

## 실행 로그

```
ingest    : 70 passed (+ 지수 백오프·서킷브레이커)
analysis  : 86 passed (+ 공분산 ERC·상태의존 FQF)
rag       : 10 passed
agents    :  9 passed
risk-engine: 40 passed (+ QS 커널 HAC·VAR prewhitening)
tui        :  9 passed
web        :  8 passed
```

## 구현 요약

| 기능 | 구현 |
|------|------|
| 공분산 ERC | `MACRO_COMBINE`=erc, `_erc_weights`(공분산 marginal risk contribution 역가중 반복) |
| 상태의존 FQF | `_FractionNet`(상태→분위수 τ), `fqf_state_dependent` 플래그, per-state taus + quantile_huber 일반화((B,Nq)) |
| 지수 백오프·서킷브레이커 | `check_timeouts` 지수 간격(ack_timeout·2^attempts), 연속실패 `cb_threshold` → open(신규 차단), `cb_cooldown` 후 half_open |
| QS 커널·prewhitening | `factor_regression_qs`(Quadratic Spectral 비절단 커널 + 대각 VAR(1) prewhiten→recolor), `qs_weight` |

## 픽스 이력

- 서킷브레이커 테스트: cooldown 초과로 half_open 조기 전환 → 오픈 직후 즉시 assert로 수정.

## MVP 범위 한계 (다음 차수 후보)

- ERC: marginal risk 역가중 휴리스틱 — Newton/SLSQP 정밀 해 미적용.
- 상태의존 FQF: FractionNet 단순 — 분위수 비율 손실(W1 거리) 별도 최적화 미적용.
- 서킷브레이커: 전역 단일 — 종목별·채널별 분리 미적용.
- QS prewhiten: 대각 VAR(1) — full VAR(1) 행렬 prewhitening 미적용.
