# test/impl/2 — F1.2~F6.2 전 기능 구현 시험 결과

**판정: PASS (65/65)**  
**일시: 2026-06-06**

## 총괄

| 영역 | 서비스 | 러너 | 결과 |
|------|--------|------|------|
| F1.2 호가창 + F1.3 뉴스 | services/ingest | pytest | ✅ 18 passed (기존 9 + 신규 9) |
| F2 지표·예측·스크리너 | services/analysis | pytest | ✅ 8 passed |
| F3.2 Quant RAG | services/rag | pytest | ✅ 6 passed |
| F3.1 멀티에이전트 | services/agents | pytest | ✅ 6 passed |
| F4 리스크 엔진 | core/risk-engine | cargo test | ✅ 10 passed |
| F6.1 스캘퍼 TUI | apps/tui | cargo test | ✅ 9 passed |
| F6.2 Web (BFF+대시보드) | web | vitest | ✅ 8 passed (bff 3 + dashboard 5) |
| **합계** | | | **✅ 65 passed, 0 failed** |

## 실행 로그 요약

```
ingest    : 18 passed in 0.30s
analysis  :  8 passed in 0.22s
rag       :  6 passed in 0.04s
agents    :  6 passed in 0.04s
risk-engine: 10 passed (cargo)
tui        :  9 passed (cargo)
bff        :  3 passed (vitest)
dashboard  :  5 passed (vitest)
```

## 픽스 이력

1. **docker-compose.yml YAML 파싱 오류** — `env_file: [.env.${ENV:-dev}]` 의 `:-` 가 flow sequence 안에서 매핑으로 오인됨. → 값 인용 `[".env.${ENV:-dev}"]` (7개 서비스). `make up` 정상화.
2. **analysis indicators 공유 DataFrame 변형** — `df.columns = [...]` in-place 변형이 mock 픽스처를 오염시켜 prediction/screener 테스트 실패. → `df.rename(columns=str.lower)` (비파괴) 로 수정.
3. **rag/agents pyproject 경량화** — 미사용 heavy deps(langchain/langgraph/pgvector/ragas) 주석화, `anthropic` 추가. MVP는 로컬 임베딩·HTTP 조합. pgvector 영속화 경로는 코드 주석 보존.
4. **web packageManager 무효 버전** — `pnpm@9` → `pnpm@9.15.0`.

## 인프라 검증 (Docker 가동)

- `make up` → postgres(pgvector:pg17) + redis 정상 기동.
- pgvector 확장 0.8.2 동작 확인 (`CREATE EXTENSION vector`).
- Redis PING → PONG.

## MVP 범위 한계 (다음 차수 후보)

- F2.2 예측: 선형회귀 — PRD의 LSTM/Transformer는 Phase 후속.
- F3.2 RAG: 인메모리 벡터스토어 — pgvector 영속화 미연동.
- F1.2 호가창: 가격기반 시뮬레이션 — 실 브로커 WebSocket 미연동.
- F6.2 대시보드: 실시간 차트 위젯 미구현(스냅샷 카드 수준).
- LLM 경로(answerer/orchestrator): ANTHROPIC_API_KEY 있을 때만 Claude, 기본 룰베이스 fallback.
