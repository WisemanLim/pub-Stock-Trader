// F6.2 실시간 캔들 차트 — 순수 기하 변환(테스트 대상). 차트 라이브러리 무의존(SVG 직접).

export interface Candle {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume?: number;
}

export interface CandleResponse {
  ticker: string;
  bars: Candle[];
  count: number;
}

// 상승/하락 색 구분 — close ≥ open 이면 상승.
export function candleColor(c: Candle): 'up' | 'down' {
  return c.close >= c.open ? 'up' : 'down';
}

// 전체 캔들의 가격 범위(high 최대 · low 최소). 빈 배열이면 0..1.
export function priceRange(candles: Candle[]): { min: number; max: number } {
  if (candles.length === 0) return { min: 0, max: 1 };
  let min = Infinity;
  let max = -Infinity;
  for (const c of candles) {
    if (c.low < min) min = c.low;
    if (c.high > max) max = c.high;
  }
  if (min === max) max = min + 1; // 평탄 시 0-division 방지
  return { min, max };
}

// 가격 → 픽셀 y (상단 0, 하단 height). 높은 값일수록 작은 y(차트 위쪽).
export function scaleY(value: number, min: number, max: number, height: number): number {
  if (max === min) return height / 2;
  return height - ((value - min) / (max - min)) * height;
}

export interface CandleRect {
  x: number;
  width: number;
  bodyY: number;
  bodyHeight: number;
  wickX: number;
  wickTop: number;
  wickBottom: number;
  color: 'up' | 'down';
}

// 캔들 배열 → SVG 렌더용 사각형/심지 좌표. width/height 픽셀 캔버스 기준.
// minPrice/maxPrice 생략 시 candles 실제 범위 사용.
export function candleLayout(
  candles: Candle[],
  width: number,
  height: number,
  gap = 2,
  minPrice?: number,
  maxPrice?: number,
): CandleRect[] {
  if (candles.length === 0) return [];
  const range = priceRange(candles);
  const min = minPrice ?? range.min;
  const max = maxPrice ?? range.max;
  const clampedMax = min === max ? max + 1 : max;
  const slot = width / candles.length;
  const bodyW = Math.max(1, slot - gap);
  return candles.map((c, i) => {
    const x = i * slot + gap / 2;
    const yOpen = scaleY(c.open, min, clampedMax, height);
    const yClose = scaleY(c.close, min, clampedMax, height);
    const bodyY = Math.min(yOpen, yClose);
    const bodyHeight = Math.max(1, Math.abs(yClose - yOpen));
    return {
      x,
      width: bodyW,
      bodyY,
      bodyHeight,
      wickX: x + bodyW / 2,
      wickTop: scaleY(c.high, min, clampedMax, height),
      wickBottom: scaleY(c.low, min, clampedMax, height),
      color: candleColor(c),
    };
  });
}

// 마우스 X 픽셀 → 캔들 인덱스. 범위 클램프. -1 = 캔들 없음.
export function findCandleIndex(x: number, candles: Candle[], width: number): number {
  if (candles.length === 0 || width <= 0) return -1;
  const slot = width / candles.length;
  const idx = Math.floor(x / slot);
  return Math.max(0, Math.min(candles.length - 1, idx));
}

// 실시간 틱 반영 — 마지막(형성 중) 캔들의 close/high/low 를 최신가로 갱신(비파괴 복사).
export function applyLivePrice(candles: Candle[], price: number): Candle[] {
  if (candles.length === 0 || !Number.isFinite(price)) return candles;
  const out = candles.slice();
  const last = { ...out[out.length - 1] };
  last.close = price;
  last.high = Math.max(last.high, price);
  last.low = Math.min(last.low, price);
  out[out.length - 1] = last;
  return out;
}
