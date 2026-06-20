import { Injectable } from '@nestjs/common';
import { serviceUrl, ServiceKey } from '../config';
import { safeTicker } from '../ticker.util';

// BFF 프록시 — 대시보드 단일 진입점에서 백엔드 마이크로서비스 집계.
@Injectable()
export class ProxyService {
  async fetchJson(key: ServiceKey, path: string): Promise<unknown> {
    const url = serviceUrl(key, path);
    const res = await fetch(url, { signal: AbortSignal.timeout(5000) });
    if (!res.ok) {
      throw new Error(`${key} ${path} → ${res.status}`);
    }
    return res.json();
  }

  // 대시보드 한 화면용 집계: 시세 + 지표 + 에이전트 시그널.
  async dashboardSnapshot(rawTicker: string, persona = 'swing') {
    const ticker = safeTicker(rawTicker); // 경로 삽입 전 검증·정규화(self-contained)
    const [price, indicators, decision] = await Promise.allSettled([
      this.fetchJson('ingest', `/market/price/${ticker}`),
      this.fetchJson('analysis', `/indicators/${ticker}`),
      this.postJson('agents', '/agents/analyze', { ticker, persona }),
    ]);
    return {
      ticker,
      persona,
      price: settled(price),
      indicators: settled(indicators),
      decision: settled(decision),
    };
  }

  // F6.2 캔들(OHLCV) 프록시 — days 정수 검증 후 ingest 호출. 다운 시 빈 결과 반환.
  async candles(rawTicker: string, rawDays: string | number) {
    const ticker = safeTicker(rawTicker);
    const days = clampDays(rawDays);
    try {
      return await this.fetchJson('ingest', `/market/ohlcv/${ticker}?days=${days}`);
    } catch {
      return { ticker, bars: [], count: 0 };
    }
  }

  // 현재가 — ingest 다운 시 null 반환(차트 폴링 오류 방지).
  async price(rawTicker: string): Promise<unknown> {
    const ticker = safeTicker(rawTicker);
    try {
      return await this.fetchJson('ingest', `/market/price/${ticker}`);
    } catch {
      return null;
    }
  }

  // 분봉 — ingest 다운 시 빈 결과 반환.
  async intraday(rawTicker: string, interval = '5m'): Promise<unknown> {
    const ticker = safeTicker(rawTicker);
    try {
      return await this.fetchJson('ingest', `/market/intraday/${ticker}?interval=${interval}`);
    } catch {
      return { ticker, bars: [], count: 0 };
    }
  }

  // 종목 검색 — ingest /krx/stocks/search 프록시. 오류 시 빈 결과 반환.
  async stocksSearch(q: string, market = 'all', limit = '10') {
    const params = new URLSearchParams({ q, market, limit });
    try {
      return await this.fetchJson('ingest', `/krx/stocks/search?${params}`);
    } catch {
      return { query: q, results: [], count: 0, total_listed: 0, cached: false };
    }
  }

  // Phase B-6: 시장경보 — ingest /krx/market-alerts 프록시.
  async marketAlerts(ticker = '') {
    const params = ticker ? `?ticker=${encodeURIComponent(ticker)}` : '';
    try {
      return await this.fetchJson('ingest', `/krx/market-alerts${params}`);
    } catch {
      return { alerts: [], count: 0, caution: 0, warning: 0, danger: 0 };
    }
  }

  // Phase B-6: 공매도 — ingest /krx/short-selling/{ticker} 프록시.
  async shortSelling(ticker: string) {
    try {
      return await this.fetchJson('ingest', `/krx/short-selling/${ticker}`);
    } catch {
      return { ticker, rows: [], count: 0 };
    }
  }

  // Phase A: 포트폴리오 — 포지션에 현재가·종목명·손익·비중 보강.
  async enrichPortfolio(account: string): Promise<unknown> {
    const raw = (await this.fetchJson('risk', `/paper/portfolio?account=${encodeURIComponent(account)}`)) as Record<string, unknown>;
    type RawPos = { ticker: string; quantity: number; avg_price: number };
    const positions: RawPos[] = Array.isArray(raw?.positions) ? (raw.positions as RawPos[]) : [];

    const enriched = await Promise.all(
      positions.map(async (p) => {
        const [priceRes, stockRes] = await Promise.allSettled([
          this.fetchJson('ingest', `/market/price/${p.ticker}`),
          this.fetchJson('ingest', `/krx/stocks/${p.ticker}`),
        ]);
        const priceData = priceRes.status === 'fulfilled' ? (priceRes.value as Record<string, unknown>) : null;
        const stockData = stockRes.status === 'fulfilled' ? (stockRes.value as Record<string, unknown>) : null;
        const currentPrice = typeof priceData?.price === 'number' ? priceData.price : null;
        const name = typeof stockData?.name === 'string' ? stockData.name : null;
        const pnl = currentPrice != null ? (currentPrice - p.avg_price) * p.quantity : null;
        const pnlPct = currentPrice != null && p.avg_price > 0 ? (currentPrice - p.avg_price) / p.avg_price : null;
        return { ...p, name, current_price: currentPrice, pnl, pnl_pct: pnlPct, weight: null as number | null };
      }),
    );

    const stockValue = enriched.reduce((s, p) => s + (p.current_price ?? p.avg_price) * p.quantity, 0);
    const cash = typeof raw?.cash === 'number' ? raw.cash : 0;
    const totalValue = stockValue + cash;
    const withWeights = enriched.map((p) => ({
      ...p,
      weight: stockValue > 0 ? ((p.current_price ?? p.avg_price) * p.quantity) / stockValue : null,
    }));

    return { ...raw, positions: withWeights, total_value: totalValue };
  }

  async postJson(key: ServiceKey, path: string, body: unknown): Promise<unknown> {
    const url = serviceUrl(key, path);
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(8000),
    });
    if (!res.ok) {
      throw new Error(`${key} ${path} → ${res.status}`);
    }
    return res.json();
  }
}

function settled<T>(r: PromiseSettledResult<T>): T | null {
  return r.status === 'fulfilled' ? r.value : null;
}

// days 정수 클램프 — URL 삽입 전 검증(1~365). 무효 → 30.
export function clampDays(raw: string | number): number {
  const n = Math.floor(Number(raw));
  if (!Number.isFinite(n) || n < 1) return 30;
  return Math.min(365, n);
}
