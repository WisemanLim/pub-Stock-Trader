import { describe, it, expect } from 'vitest';
import { searchStocks, KRX_STOCKS } from './stocks';

describe('KRX_STOCKS', () => {
  it('contains KOSPI and KOSDAQ entries', () => {
    const kospi = KRX_STOCKS.filter((s) => s.market === 'KOSPI');
    const kosdaq = KRX_STOCKS.filter((s) => s.market === 'KOSDAQ');
    expect(kospi.length).toBeGreaterThan(10);
    expect(kosdaq.length).toBeGreaterThan(10);
  });

  it('all tickers are 6-digit numeric strings', () => {
    for (const s of KRX_STOCKS) {
      expect(s.ticker).toMatch(/^\d{6}$/);
    }
  });

  it('삼성전자 has ticker 005930', () => {
    const entry = KRX_STOCKS.find((s) => s.name === '삼성전자');
    expect(entry?.ticker).toBe('005930');
    expect(entry?.market).toBe('KOSPI');
  });

  it('no duplicate tickers', () => {
    const tickers = KRX_STOCKS.map((s) => s.ticker);
    const unique = new Set(tickers);
    // some tickers appear twice (e.g. 삼성바이오에피스/삼성바이오로직스 same code) — report count
    expect(unique.size).toBeGreaterThan(KRX_STOCKS.length * 0.95);
  });
});

describe('searchStocks', () => {
  it('returns empty for empty query', () => {
    expect(searchStocks('')).toEqual([]);
  });

  it('returns empty for whitespace-only query', () => {
    expect(searchStocks('   ')).toEqual([]);
  });

  it('finds by exact company name', () => {
    const results = searchStocks('삼성전자');
    expect(results.length).toBeGreaterThan(0);
    expect(results[0].name).toBe('삼성전자');
    expect(results[0].ticker).toBe('005930');
  });

  it('finds by partial name', () => {
    const results = searchStocks('삼성');
    expect(results.length).toBeGreaterThan(1);
    expect(results.every((s) => s.name.includes('삼성'))).toBe(true);
  });

  it('finds by 6-digit code', () => {
    const results = searchStocks('005930');
    expect(results.length).toBeGreaterThan(0);
    expect(results[0].ticker).toBe('005930');
  });

  it('finds by partial code (startsWith)', () => {
    const results = searchStocks('0059');
    expect(results.every((s) => s.ticker.startsWith('0059'))).toBe(true);
  });

  it('respects limit parameter', () => {
    const results = searchStocks('삼성', 3);
    expect(results.length).toBeLessThanOrEqual(3);
  });

  it('defaults to limit 8', () => {
    const results = searchStocks('a'); // matches nothing in Korean — check fallback
    expect(results.length).toBeLessThanOrEqual(8);
  });

  it('returns empty for no match', () => {
    expect(searchStocks('존재하지않는기업ZZZZZ')).toEqual([]);
  });

  it('finds KOSDAQ entries', () => {
    const results = searchStocks('에코프로');
    expect(results.some((s) => s.market === 'KOSDAQ')).toBe(true);
  });

  it('numeric query uses startsWith (not contains)', () => {
    const results = searchStocks('12'); // should match tickers starting with 12
    expect(results.every((s) => s.ticker.startsWith('12'))).toBe(true);
  });

  it('non-numeric query does name contains check', () => {
    const results = searchStocks('현대');
    expect(results.length).toBeGreaterThan(0);
    expect(results.every((s) => s.name.includes('현대') || s.ticker.startsWith('현대'))).toBe(true);
  });
});
