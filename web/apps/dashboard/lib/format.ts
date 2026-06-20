// 대시보드 표시용 순수 포맷 유틸 (테스트 대상).

export function formatPrice(v: number | null | undefined): string {
  if (v == null || Number.isNaN(v)) return '-';
  return v.toLocaleString('ko-KR', { maximumFractionDigits: 0 });
}

export function formatPct(v: number | null | undefined): string {
  if (v == null || Number.isNaN(v)) return '-';
  const sign = v > 0 ? '+' : '';
  return `${sign}${v.toFixed(2)}%`;
}

export function signalColor(signal: string | null | undefined): string {
  switch (signal) {
    case 'BUY':
      return 'text-green-600';
    case 'SELL':
      return 'text-red-600';
    default:
      return 'text-gray-500';
  }
}

export interface DashboardSnapshot {
  ticker: string;
  persona: string;
  price: { price: number; volume: number } | null;
  indicators: {
    rsi: number | null;
    signal: string;
    close: number;
    macd?: { macd: number; signal: number; histogram: number } | null;
    atr?: number | null;
    bollinger?: { upper: number; middle: number; lower: number; bandwidth: number } | null;
    ema_20?: number | null;
    sma_50?: number | null;
    vwap_20?: number | null;
    close_pct?: number | null;
  } | null;
  decision: { decision: { signal: string; weight: number; confidence: number } } | null;
}
