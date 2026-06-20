# test/impl/19 — 차수 19 고도화 시험 결과

**판정: PASS (287/287)**
**일시: 2026-06-07**

## 총괄

| 영역 | 서비스 | 러너 | 결과 |
|------|--------|------|------|
| 격자 QuEST 수치역전 + 기존 | analysis | pytest | ✅ 116 |
| 채널별 토큰버킷 + 기존 | ingest | pytest | ✅ 83 |
| pgvector + 인메모리 | rag | pytest | ✅ 10 |
| 알림 + 멀티에이전트 | agents | pytest | ✅ 9 |
| 리스크 + companion 복소 고유값 클리핑(QR) | risk-engine | cargo | ✅ 52 |
| TUI | apps/tui | cargo | ✅ 9 |
| Web | web | vitest | ✅ 8 |
| **합계** | | | **✅ 287 passed, 0 failed** |

## 실행 로그

```
ingest    : 83 passed (+ 채널별 토큰버킷)
analysis  : 116 passed (+ 격자 QuEST 수치역전 + 멀티프로세스 롤아웃)
rag       : 10 passed
agents    :  9 passed
risk-engine: 52 passed (+ companion 복소 고유값 QR 반경)
tui        :  9 passed
web        :  8 passed (bff 3 + dashboard 5)
```

## 구현 요약

| 기능 | 구현 |
|------|------|
| 격자 QuEST 수치역전 | `_quest_grid_shrink`(고유값 support 격자 200점 + Epanechnikov 밀도 + 수치 Hilbert 주값적분 → np.interp 로 표본 λ를 격자 oracle 고유값에 사상), `MACRO_COMBINE=erc_quest_grid`. p≥n 폴백 |
| 멀티프로세스 롤아웃 | dpg `executor="process"`(`ProcessPoolExecutor` + `_process_rollout` 워커, policy `state_dict` 복제로 피클·독립 실행), 롤아웃별 시드 → 순차=프로세스 동일(결정적). 결과 dict `executor` 표기 |
| 채널별 토큰버킷 | `channel_rates`(ch→rate·cap), `_tb_ch` 채널별 버킷 + `_bucket_refill`, `_tb_consume(channel)` 채널 버킷 우선 후 전역, `tokens_available(channel)`, `add(channel=)` |
| companion 복소 고유값 클리핑 | `qr_eigen_magnitudes`(비시프트 QR 반복 + 2x2 블록 복소공액 |λ|=√det), `qr_decompose`(Gram-Schmidt), `companion_radius_qr`, `factor_regression_qs_var_full(companion)` 가 QR 반경 사용 |

## 픽스 이력

- 없음(신규 추가, 기존 회귀 전부 통과).

## 거시 합성 모드 (총 15종)
mean·weighted·dynamic·riskparity·erc·erc_newton·erc_lw·erc_cc·erc_oas·erc_nlw·erc_quest·**erc_quest_grid**·pca·ipca·ccipca

## MVP 범위 한계 (다음 차수 후보)

- 격자 QuEST: 고정 격자(200) + Epanechnikov 단일 커널 — 적응 격자·MP 적합도 검정·QuESTimate 반복 미적용.
- 멀티프로세스: spawn 워커 매 에피소드 재생성(state_dict 전송) — 영속 워커풀·공유메모리 텐서 미적용.
- 토큰버킷: rate·capacity 고정 — 우선순위 큐·적응형 rate(AIMD) 미적용.
- companion: QR 반경 스케일 사영 — 개별 복소 고유값 위상보존 클리핑(완전 Schur 분해) 미적용.
