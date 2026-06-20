import { describe, it, expect } from 'vitest';
import { formatPrice, formatPct, signalColor } from './format';

describe('dashboard format utils', () => {
  it('formats price with thousands separator', () => {
    expect(formatPrice(73500)).toBe('73,500');
  });

  it('handles null price', () => {
    expect(formatPrice(null)).toBe('-');
    expect(formatPrice(undefined)).toBe('-');
  });

  it('formats positive pct with sign', () => {
    expect(formatPct(2.1)).toBe('+2.10%');
  });

  it('formats negative pct', () => {
    expect(formatPct(-1.5)).toBe('-1.50%');
  });

  it('maps signal to color class', () => {
    expect(signalColor('BUY')).toContain('green');
    expect(signalColor('SELL')).toContain('red');
    expect(signalColor('HOLD')).toContain('gray');
    expect(signalColor(null)).toContain('gray');
  });
});
