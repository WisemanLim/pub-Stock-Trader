# test/impl/19 — 차수 19 고도화 시험 시나리오

**범위**: 격자 QuEST 수치역전 · 멀티프로세스(모델 복제) 병렬 롤아웃 · 채널별 토큰버킷 · companion 복소 고유값 클리핑(Schur/QR)
**차수**: 19
**러너**: pytest(Python) · cargo test(Rust) · vitest(Web)

## 격자 QuEST 수치역전 (services/analysis)

| TC | 시나리오 | 기대 |
|----|----------|------|
| GQ-01 | 격자 QuEST 축소 PSD·대칭 | PSD, 대칭 |
| GQ-02 | erc_quest_grid 합성 | finite weight |

## 멀티프로세스 병렬 롤아웃 (services/analysis)

| TC | 시나리오 | 기대 |
|----|----------|------|
| PR-01 | process executor=순차 결과 | 동일 final_equity, executor="process" |
| PR-02 | 단일 롤아웃 executor 표기 | "none" |

## 채널별 토큰버킷 (services/ingest)

| TC | 시나리오 | 기대 |
|----|----------|------|
| CB-01 | 채널별 rate/capacity 버스트→차단 | 채널 버킷 소진 후 차단 |
| CB-02 | 채널 버킷 독립(타 채널 영향 없음) | 타 채널 허용 |
| CB-03 | 전역+채널 동시 적용 | 둘 중 부족하면 차단 |

## companion 복소 고유값 클리핑 (core/risk-engine)

| TC | 시나리오 | 기대 |
|----|----------|------|
| QR-01 | QR 고유값 크기(실·복소공액) | |λ| 정확(2x2 블록 det) |
| QR-02 | companion_radius_qr 복소 | power-iter 대비 정확한 반경 |

## 금융 규제 케이스 (COMPLIANCE.md)

- **정밀 추정**: 격자 QuEST 수치역전(고유값 support 격자 + Hilbert 주값적분) → 해석적 대비 임의 분포 oracle 근사.
- **재현·확장**: 멀티프로세스(state_dict 복제) 롤아웃별 시드 → 순차=프로세스 동일(결정적·감사) + GIL 우회 확장.
- **처리율 보호**: 채널별 토큰버킷 → 채널 단위 격리(한 채널 폭주가 타 채널 잠식 방지).
- **정상성 정확**: companion 복소 고유값 QR(Schur 2x2 블록) → 복소공액쌍 반경 정확 → VAR 안정성 사영 신뢰.
