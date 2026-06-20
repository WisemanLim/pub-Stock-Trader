# test/impl/18 — 차수 18 고도화 시험 시나리오

**범위**: QuEST 정밀 비선형축소 · 멀티(스레드) 병렬 롤아웃 · 토큰버킷 처리율 제한 · companion 고유값 사영
**차수**: 18
**러너**: pytest(Python) · cargo test(Rust)

## QuEST 비선형축소 (services/analysis)

| TC | 시나리오 | 기대 |
|----|----------|------|
| QU-01 | QuEST 축소 PSD·대칭 | PSD, 대칭 |
| QU-02 | p>n 폴백 | 원본 반환 |
| QU-03 | erc_quest 합성 | finite |

## 멀티 병렬 롤아웃 (services/analysis)

| TC | 시나리오 | 기대 |
|----|----------|------|
| MP-01 | 스레드풀=순차 결과 | 동일 final_equity |
| MP-02 | 단일 롤아웃 parallel=False 표기 | False |

## 토큰버킷 처리율 (services/ingest)

| TC | 시나리오 | 기대 |
|----|----------|------|
| TB-01 | rate/capacity 버스트→차단→충전 | 버킷 소진·충전 후 허용 |
| TB-02 | 무제한 기본 | 전부 허용 |
| TB-03 | 중복 미소비 | 토큰 보존 |

## companion 고유값 사영 (core/risk-engine)

| TC | 시나리오 | 기대 |
|----|----------|------|
| CO-01 | companion 안정성 사영 | 유한 SE |
| CO-02 | companion 행렬·반경 | 시프트 항등·반경<1 |

## 금융 규제 케이스 (COMPLIANCE.md)

- **정밀 추정**: QuEST 해석적 비선형축소(MP/커널밀도) → 고유값 oracle 근사(소표본 최적).
- **재현·확장**: 병렬 롤아웃 롤아웃별 시드 → 순차=병렬 동일(결정적·감사) + 처리량 확장.
- **처리율 보호**: 토큰버킷 → 구독 폭주 방지(브로커 rate limit 준수).
- **정상성 정확**: companion 고유값 반경(p>1 정확) → VAR 안정성 사영 신뢰.
