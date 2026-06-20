import { describe, it, expect } from 'vitest';
import { BadRequestException } from '@nestjs/common';
import { safeTicker } from './ticker.util';

describe('safeTicker', () => {
  it('accepts KR numeric and US alpha, uppercases', () => {
    expect(safeTicker('005930')).toBe('005930');
    expect(safeTicker('aapl')).toBe('AAPL');
  });

  it('rejects path traversal and separators', () => {
    for (const bad of ['../etc', '005930/x', 'a.b', '..', 'a b', 'a?b', 'a#b', '']) {
      expect(() => safeTicker(bad)).toThrow(BadRequestException);
    }
  });

  it('rejects over-long input', () => {
    expect(() => safeTicker('A'.repeat(21))).toThrow(BadRequestException);
  });
});
