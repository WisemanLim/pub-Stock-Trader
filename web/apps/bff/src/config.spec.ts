import { describe, it, expect } from 'vitest';
import { serviceUrl, SERVICES } from './config';

describe('BFF config', () => {
  it('builds service url with leading slash', () => {
    expect(serviceUrl('ingest', '/market/price/005930')).toBe(
      `${SERVICES.ingest}/market/price/005930`,
    );
  });

  it('builds service url without leading slash', () => {
    expect(serviceUrl('analysis', 'indicators/005930')).toBe(
      `${SERVICES.analysis}/indicators/005930`,
    );
  });

  it('has all 5 backend services', () => {
    expect(Object.keys(SERVICES).sort()).toEqual(
      ['agents', 'analysis', 'ingest', 'rag', 'risk'].sort(),
    );
  });
});
