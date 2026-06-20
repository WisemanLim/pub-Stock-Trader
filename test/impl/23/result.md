# test/impl/23 — 차수 23 계정 다중화 시험 결과

**판정: PASS (386/386)**
**일시: 2026-06-07**

## 총괄

| 영역 | 서비스 | 러너 | 결과 |
|------|--------|------|------|
| F5 가상체결 **계정 다중화** + 기존 | risk-engine | cargo | ✅ 72 |
| analysis | analysis | pytest | ✅ 128 |
| ingest | ingest | pytest | ✅ 105 |
| rag | rag | pytest | ✅ 10 |
| agents | agents | pytest | ✅ 36 |
| tui | apps/tui | cargo | ✅ 9 |
| web | dashboard+bff | vitest | ✅ 26 |
| **합계** | | | **✅ 386 passed, 0 failed** |

차수22 381 → 차수23 386 (+5, risk-engine 67→72). clean build(no warning).

## 구현 요약

| 항목 | 구현 |
|------|------|
| 계정 레지스트리 | `paper.rs`: 단일 `BOOK` → `BOOKS: Mutex<HashMap<String,PaperBook>>`. `with_account_book(account,f)`(신규 생성·poison 복구) + `with_book`=기본 계정(하위호환) + `list_accounts()` |
| 계정 라우팅 | `main.rs`: `?account=` 쿼리 → execute·portfolio·control(halt/status/liquidate) 계정 인지. 신규 `GET /paper/accounts` |
| DB durability 범위 | 기본 계정만 영속화(paper_fills 계정 미구분). 명명 계정 인메모리 격리. 기존 DB-우선 durability·하이드레이션 경로 불변 |
| 하위호환 | with_book→default 유지 → 기존 핸들러(mark·equity·factor regression)·67 테스트 무회귀 |

## 실행 로그

```
risk-engine: 72 passed (paper/risk 기존 67 + 계정 다중화 5)
  accounts_are_isolated / with_book_targets_default_account
  list_accounts_includes_created / halt_is_per_account / liquidate_is_per_account
cargo build: clean (no warning)
```

## 픽스 이력
- 무수정 1회 통과(0 fail). `BOOK` 정적 직접참조 없음 확인(주석만) → 레지스트리 교체 안전.
- poison 복구 테스트(`with_book_recovers_from_poison`)는 기본 계정 경유 → 정상.

## 보류 항목(근거)
- **위상보존 Schur 클리핑**: companion 행렬은 유사변환(Q T Qᵀ) 시 companion 구조(하단 항등 시프트)가
  깨져 클리핑된 고유값을 VAR 계수 A_l 로 역사상할 수 없음. 현 `companion_radius_qr` 균일 스케일 사영이
  companion 에 유효. 위상보존 per-eigenvalue 클리핑은 고유벡터(Vandermonde) 재구성 필요 → 별도 설계.

## 검증 커맨드
```bash
export PATH=$HOME/.cargo/bin:$PATH
cargo test -p risk-engine                         # 72
cargo test --workspace                            # risk 72 + tui 9
```
