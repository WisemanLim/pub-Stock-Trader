# test/impl/23 — 차수 23 시험 시나리오

**대상:** F5 가상체결 **계정 다중화(multi-account)**.
PRD 다음 단계 "가상체결 … 계정 다중화" 완료. (위상보존 Schur 클리핑은 companion 유사변환이
companion 구조를 깨 VAR 계수로의 역사상이 불가 → 별도 검토로 보류.)
**하위호환·가산** — 기본 계정("default") 동작·DB 영속화 경로 불변 → 기존 67건 무회귀.

## 구현

- `paper.rs`: 전역 단일 `BOOK` → 계정별 레지스트리 `BOOKS: Mutex<HashMap<String, PaperBook>>`.
  - `with_account_book(account, f)` — 계정별 원장 접근(신규 생성, poison 복구).
  - `with_book(f)` = `with_account_book("default", f)` (하위호환: 하이드레이션·mark·분석 라우트).
  - `list_accounts()` — 등록 계정 정렬 목록.
- `main.rs`: `?account=` 쿼리로 계정 라우팅.
  - `paper_execute`/`paper_portfolio`/`control_halt`/`control_status`/`control_liquidate` 계정 인지.
  - 신규 `GET /paper/accounts` — 계정 목록.
  - **DB durability 는 기본 계정만**(paper_fills 계정 미구분 → 명명 계정은 인메모리 격리). 기존 영속화 경로 불변.

## 시나리오 (검증 케이스, cargo)

| # | 테스트 | 검증 |
|---|--------|------|
| 1 | `accounts_are_isolated` | 두 계정 동일 종목 매수 → 포지션 격리(10 vs 3) |
| 2 | `with_book_targets_default_account` | with_book == 기본 계정(하위호환) |
| 3 | `list_accounts_includes_created` | 생성 계정이 목록에 포함 |
| 4 | `halt_is_per_account` | kill-switch 계정별 독립 |
| 5 | `liquidate_is_per_account` | A 청산 후 B 보유 유지(격리) |
| 6 | 기존 67건 | 무회귀(default 경로·DB durability 불변) |

## 규제(COMPLIANCE/finance)
- 계정별 원장 격리 — 무권한 교차계정 영향 차단(전자금융 책임추적). append-only 원장·멱등키 계정별 유지.
- Fail-Safe: 계정별 halt/청산 독립. poison 복구 유지(가용성).
- 영속화 한계 명시: 명명 계정은 인메모리(재시작 비영속), 기본 계정만 DB 하이드레이션.

## 판정 기준
- `cargo test -p risk-engine` 전건 PASS, 기존 paper/risk 무회귀, clean build(no warning).
