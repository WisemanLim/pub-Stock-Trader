import { BadRequestException } from '@nestjs/common';

// 종목 코드 화이트리스트 — KR 숫자코드(005930)·US 알파(AAPL). 영숫자만 1~20자.
// 경로 인젝션(`../`, 쿼리·세그먼트) 차단: 슬래시·점·기호 불허.
const TICKER_RE = /^[A-Za-z0-9]{1,20}$/;

/** ticker 검증 + 정규화(대문자). 백엔드 URL 경로에 삽입 전 호출. 무효 → 400. */
export function safeTicker(raw: string): string {
  const t = (raw ?? '').toUpperCase();
  if (!TICKER_RE.test(t)) {
    throw new BadRequestException(`invalid ticker: ${raw}`);
  }
  // 영숫자만 통과하므로 encodeURIComponent 는 사실상 항등 — 다중 방어 차원.
  return encodeURIComponent(t);
}
