import type { DashboardSnapshot } from './format';
import type { CandleResponse } from './candles';

const BFF_URL = process.env.BFF_URL ?? 'http://localhost:3002';

// F6.2 캔들(OHLCV) — BFF 경유 ingest 프록시.
export async function getCandles(ticker: string, days = 30): Promise<CandleResponse> {
  const res = await fetch(`${BFF_URL}/api/candles/${ticker}?days=${days}`, {
    cache: 'no-store',
  });
  if (!res.ok) {
    throw new Error(`BFF candles ${ticker} → ${res.status}`);
  }
  return res.json();
}

export interface StockMeta {
  found: boolean;
  ticker: string;
  name: string | null;
  market: string | null;
}

// 단일 종목 메타 (name, market) — Next.js /api/stocks/:ticker 경유.
export async function getStockMeta(ticker: string): Promise<StockMeta> {
  try {
    const res = await fetch(`/api/stocks/${ticker}`, {
      cache: 'no-store',
      signal: AbortSignal.timeout(3000),
    });
    if (!res.ok) return { found: false, ticker, name: null, market: null };
    return res.json();
  } catch {
    return { found: false, ticker, name: null, market: null };
  }
}

// 대시보드 집계 데이터 — BFF 단일 호출.
export async function getSnapshot(
  ticker: string,
  persona = 'swing',
): Promise<DashboardSnapshot> {
  const res = await fetch(`${BFF_URL}/api/dashboard/${ticker}?persona=${persona}`, {
    cache: 'no-store',
    signal: AbortSignal.timeout(5000),
  });
  if (!res.ok) {
    throw new Error(`BFF dashboard ${ticker} → ${res.status}`);
  }
  return res.json();
}
