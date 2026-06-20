import { describe, it, expect } from 'vitest';
import {
  candleColor,
  priceRange,
  scaleY,
  candleLayout,
  applyLivePrice,
  findCandleIndex,
  type Candle,
} from './candles';

const C = (open: number, high: number, low: number, close: number): Candle => ({
  date: '2024-01-01',
  open,
  high,
  low,
  close,
});

describe('candle geometry', () => {
  it('marks up/down by close vs open', () => {
    expect(candleColor(C(100, 110, 95, 105))).toBe('up');
    expect(candleColor(C(105, 110, 95, 100))).toBe('down');
    expect(candleColor(C(100, 110, 95, 100))).toBe('up'); // 동가 → 상승
  });

  it('computes price range across highs and lows', () => {
    const r = priceRange([C(100, 120, 90, 110), C(110, 130, 105, 115)]);
    expect(r.min).toBe(90);
    expect(r.max).toBe(130);
  });

  it('defaults range for empty input', () => {
    expect(priceRange([])).toEqual({ min: 0, max: 1 });
  });

  it('avoids zero-division on flat range', () => {
    const r = priceRange([C(100, 100, 100, 100)]);
    expect(r.max).toBeGreaterThan(r.min);
  });

  it('scales high value to small y (chart top)', () => {
    expect(scaleY(100, 0, 100, 200)).toBe(0); // 최대값 → 상단(y=0)
    expect(scaleY(0, 0, 100, 200)).toBe(200); // 최소값 → 하단
    expect(scaleY(50, 0, 100, 200)).toBe(100); // 중간
  });

  it('lays out one rect per candle within canvas', () => {
    const rects = candleLayout([C(100, 110, 95, 105), C(105, 115, 100, 110)], 100, 200);
    expect(rects).toHaveLength(2);
    expect(rects[0].x).toBeGreaterThanOrEqual(0);
    expect(rects[0].bodyHeight).toBeGreaterThanOrEqual(1);
    expect(rects[0].wickTop).toBeLessThanOrEqual(rects[0].wickBottom); // top(작은 y) ≤ bottom
  });

  it('returns empty layout for no candles', () => {
    expect(candleLayout([], 100, 200)).toEqual([]);
  });

  it('accepts custom minPrice/maxPrice for padded range', () => {
    const candle = C(100, 110, 95, 105);
    const [r] = candleLayout([candle], 100, 200, 2, 80, 130);
    // 110(high) scaled in 80..130 range should be above 95(low)
    expect(r.wickTop).toBeLessThan(r.wickBottom);
    // body should be within chart area
    expect(r.bodyY).toBeGreaterThanOrEqual(0);
    expect(r.bodyY + r.bodyHeight).toBeLessThanOrEqual(200 + 1);
  });

  it('candleLayout without minPrice/maxPrice behaves same as before', () => {
    const rects1 = candleLayout([C(100, 110, 95, 105)], 100, 200);
    const { min, max } = priceRange([C(100, 110, 95, 105)]);
    const rects2 = candleLayout([C(100, 110, 95, 105)], 100, 200, 2, min, max);
    expect(rects1[0].bodyY).toBeCloseTo(rects2[0].bodyY, 1);
  });
});

describe('realtime live price', () => {
  it('updates last candle close/high/low', () => {
    const out = applyLivePrice([C(100, 110, 95, 105)], 120);
    expect(out[0].close).toBe(120);
    expect(out[0].high).toBe(120); // 신고가
    expect(out[0].low).toBe(95);
  });

  it('lowers low on new low price', () => {
    const out = applyLivePrice([C(100, 110, 95, 105)], 90);
    expect(out[0].low).toBe(90);
    expect(out[0].close).toBe(90);
  });

  it('is non-destructive (copies input)', () => {
    const input = [C(100, 110, 95, 105)];
    const out = applyLivePrice(input, 120);
    expect(input[0].close).toBe(105); // 원본 불변
    expect(out).not.toBe(input);
  });

  it('ignores non-finite price', () => {
    const input = [C(100, 110, 95, 105)];
    expect(applyLivePrice(input, NaN)).toBe(input);
  });
});

describe('findCandleIndex (tooltip lookup)', () => {
  const candles = [C(100, 110, 95, 105), C(105, 115, 100, 110), C(110, 120, 105, 115)];

  it('returns 0 for leftmost pixel', () => {
    expect(findCandleIndex(0, candles, 300)).toBe(0);
  });

  it('returns last index for rightmost pixel', () => {
    expect(findCandleIndex(299, candles, 300)).toBe(2);
  });

  it('returns correct middle index', () => {
    // slot = 300/3 = 100. pixel 150 → index 1
    expect(findCandleIndex(150, candles, 300)).toBe(1);
  });

  it('returns -1 for empty candles', () => {
    expect(findCandleIndex(50, [], 300)).toBe(-1);
  });

  it('returns -1 for zero width', () => {
    expect(findCandleIndex(50, candles, 0)).toBe(-1);
  });

  it('clamps out-of-bounds x to last index', () => {
    expect(findCandleIndex(9999, candles, 300)).toBe(2);
  });
});
