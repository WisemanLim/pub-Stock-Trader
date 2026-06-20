# COMPLIANCE.md — Finance (금융·증권) 도메인 규제·데이터등급

> 생성: wise-dev-standard scaffold — finance 도메인 오버레이 (KSIC K)
> **중요**: 본 문서는 프로젝트 설계 가이드라인입니다. 실제 규제 적합성은 법무·보안 담당자와 반드시 검토하십시오.

---

## 1. 한국 핵심 규제

| 규제 | 시행일 | 핵심 영향 |
|---|---|---|
| 전자금융거래법 | 현행 | 무권한거래 책임 → 인증·로깅·책임추적 설계 필수 (브로커리지 API 연동) |
| 전자금융감독규정 | 2025-02-05 | 망분리 위험기반 예외, SaaS 별도기준, 가명정보 R&D 허용 |
| 신용정보법 | 현행 | 개인신용정보 가명/익명 처리, 비프로드 반출 통제 |
| 개인정보보호법(PIPA) | 현행 | 암호화·접근통제·유출통지 기본선 |
| ISMS-P | 2025 강화 | 접근로그·변경관리·암호화 증적, 위반 시 인증취소 |
| 마이데이터(MyData 2.0) | 2025-06-19 | 표준 전송 API + 동의원장 + 강인증/암호화 |
| 재해복구센터(DR) | 2026 단계적 | DR/BCP 인프라 아키텍처 필수 (F4 Fail-Safe 모드와 직결) |

## 2. 국제 기준

- **PCI-DSS 4.0.1** (2025-03-31 all best-practices mandatory): CDE 전구간 MFA, 카드데이터 토큰화
- **SOC 2 Type II**: 보안·가용성·처리무결성
- **PSD2 SCA/RBA**: 해외·EU 연계 시
- **ISO 20022**: 결제 메시지 표준
- **DORA/PQC**: crypto-agility 대비 (PQC 전환 계획 수립 필요)

## 3. 데이터 등급 및 처리 규칙

| 등급 | 데이터 종류 | 처리 규칙 |
|---|---|---|
| 🔴 규제대상 | 개인신용정보, 결제·카드(CHD/SAD), 인증·API키 | 비프로드 환경 반입 절대 금지. HSM/KMS 격리. 토큰화. |
| 🟠 민감 | PII(이름·연락처·주소), 계좌번호 | PIPA 준수. 암호화 필수. |
| 🟡 제한 | 가명정보·익명정보 | R&D 사용 가능(2025 개정). 재식별 방지. |
| 🟢 무결성 필수 | 거래원장·감사로그·체결기록 | append-only. 변조방지. 불변 감사추적 (ISMS-P). |
| ⚪ 일반 | 기술지표·뉴스·공시·가격 데이터 | 일반 접근통제 |

### ⚠️ 개발 환경 필수 규칙

1. `.env.local` **비프로덕션 환경에 실 개인신용정보·결제데이터 절대 반입 금지**
2. 개발·테스트용 데이터는 **합성 데이터(synthetic)** 또는 **가명처리된 데이터** 만 사용
3. 증권사 API Key/Secret → **OS Keychain** (로컬) 또는 **HashiCorp Vault** 보관
   - 파일·코드·git commit 노출 절대 금지
4. 코드→배포 **불변 감사추적** 필수 (GitHub Actions 서명 커밋, ISMS-P 증적)

## 4. 인프라 설계 요건

### 4.1 멱등성 & 원장 (F4 연관)

- 모든 주문 API에 **Idempotency-Key** 헤더 강제 → 중복 요청 1건만 처리
- 거래 원장 테이블: PostgreSQL ACID + **Transactional Outbox** 패턴 (exactly-once 이벤트)
- 정산 대사(reconciliation) 잡: 외부 브로커 레일 vs 원장 금액 일치 검증

### 4.2 키 & 암호화

- 로컬 개발: **OS Keychain** 또는 Vault Dev Server
- K8s prod: **External Secrets Operator** + 클라우드 KMS (AWS KMS / GCP KMS)
- crypto-agility: PQC(Post-Quantum) 전환 가능 아키텍처 (DORA 대비)

### 4.3 네트워크 분리 (CDE)

- 증권사 API 연동 경로: **CDE(Cardholder Data Environment) 네트워크 격리**
- K8s: NetworkPolicy + ServiceMesh(Istio/Linkerd) 권장
- 2025 개정: 비핵심·무개인신용정보 워크로드 → 클라우드 SaaS 조건부 허용

### 4.4 감사 로그

- 모든 주문·체결·리스크 판단 이벤트: **append-only 감사로그** (변조방지)
- 로그 스트리밍: Redis Streams → 감사 DB + SIEM 연동

### 4.5 Fail-Safe & DR (F4 NFR 직결)

- **브로커리지 세션 유실 시**: 즉시 신규 매수 전면 차단 + 모니터링 알림 (Fail-Safe 모드)
- **일일 최대손실 한도 초과**: 추가 신규 매수 전면 금지 + 기존 포지션 단계적 청산
- DR/BCP 요건 (2026): 복구목표시간(RTO/RPO) 설계 문서 필요

## 5. 추가 시험 항목 (testing_additions)

`test/impl/<Nth>/` 에 시나리오·결과 저장.

| 시험 항목 | 기대 결과 |
|---|---|
| 멱등 주문 (중복 요청) | 동일 Idempotency-Key → 주문 1건만 생성됨 |
| 정산 대사 | 외부 브로커 레일 체결 금액 == 원장 기록 금액 |
| ORDER_FAILED 보상 트랜잭션 | 주문 실패 시 잔액·포지션 원복 확인 |
| Stop-Loss 강제 체결 | -2% 도달 시 **10ms 이내** 시장가 매도 주문 송출 |
| 일일 최대손실 한도 | -5% 초과 시 신규 매수 전면 차단 + 알림 |
| 브로커 세션 유실 Fail-Safe | 연결 끊김 → 신규 진입 차단 + Telegram 알림 |
| CDE 접근 MFA 강제 | MFA 없는 CDE 접근 → 거부 확인 |
| API Key 노출 방지 | git log / .env 파일에 실 키 미노출 확인 |

## 6. 출처

- [전자금융감독규정 개정 (2025-02-05)](https://www.fsc.go.kr/no010101/82885)
- [망분리 개선 로드맵](https://www.fsc.go.kr/no010101/84780)
- [PCI-DSS 4.0.1](https://www.pcisecuritystandards.org/)
- [ISMS-P 인증기준 (KISA)](https://isms.kisa.or.kr/)
- [신용정보법 (국가법령정보센터)](https://www.law.go.kr/법령/신용정보의이용및보호에관한법률)
