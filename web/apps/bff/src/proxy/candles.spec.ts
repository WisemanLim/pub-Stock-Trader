import { describe, it, expect } from 'vitest';
import { clampDays } from './proxy.service';

describe('clampDays (F6.2 candles)', () => {
  it('passes through valid integer', () => {
    expect(clampDays('30')).toBe(30);
    expect(clampDays(60)).toBe(60);
  });

  it('floors fractional', () => {
    expect(clampDays('45.9')).toBe(45);
  });

  it('defaults invalid to 30', () => {
    expect(clampDays('abc')).toBe(30);
    expect(clampDays('0')).toBe(30);
    expect(clampDays('-5')).toBe(30);
  });

  it('caps at 365', () => {
    expect(clampDays('100000')).toBe(365);
  });
});
