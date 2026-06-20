'use client';
import { useEffect, useRef, useState, useMemo } from 'react';

const BFF = process.env.NEXT_PUBLIC_BFF_URL ?? 'http://localhost:3002';

type OhlcvBar = { date: string; open: number; high: number; low: number; close: number };

type Position = {
  ticker: string; name?: string; quantity: number; avg_price: number;
  cost_basis?: number;
  current_price?: number; pnl?: number; pnl_pct?: number; weight?: number;
};

type Portfolio = {
  account?: string; cash?: number; total_value?: number;
  positions: Position[];
};

type PortSortKey = 'ticker' | 'name' | 'quantity' | 'avg_price' | 'buy_amount' | 'current_price' | 'sell_amount' | 'pnl' | 'pnl_pct' | 'weight';
type SortDir = 'asc' | 'desc';

const PORT_COLS: { key: PortSortKey; label: string }[] = [
  { key: 'ticker',        label: '종목코드'   },
  { key: 'name',          label: '종목명'     },
  { key: 'quantity',      label: '보유수량'   },
  { key: 'avg_price',     label: '매수시단가' },
  { key: 'buy_amount',    label: '매수총금액' },
  { key: 'current_price', label: '현재가'     },
  { key: 'sell_amount',   label: '매도총금액' },
  { key: 'pnl',           label: '평가손익'   },
  { key: 'pnl_pct',       label: '수익률'     },
  { key: 'weight',        label: '비중'       },
];

function portValue(p: Position, key: PortSortKey): number | string | null {
  switch (key) {
    case 'ticker':        return p.ticker;
    case 'name':          return p.name ?? '';
    case 'quantity':      return p.quantity ?? null;
    case 'avg_price':     return p.avg_price;
    case 'buy_amount':    return p.cost_basis ?? p.avg_price * (p.quantity ?? 0);
    case 'current_price': return p.current_price ?? null;
    case 'sell_amount':   return p.current_price != null ? p.current_price * (p.quantity ?? 0) : null;
    case 'pnl':           return p.pnl ?? null;
    case 'pnl_pct':       return p.pnl_pct ?? null;
    case 'weight':        return p.weight ?? null;
  }
}

function sortPositions(rows: Position[], key: PortSortKey, dir: SortDir): Position[] {
  return [...rows].sort((a, b) => {
    const av = portValue(a, key);
    const bv = portValue(b, key);
    if (av == null && bv == null) return 0;
    if (av == null) return 1;
    if (bv == null) return -1;
    let cmp = 0;
    if (typeof av === 'string' && typeof bv === 'string') cmp = av.localeCompare(bv, 'ko');
    else cmp = (av as number) < (bv as number) ? -1 : (av as number) > (bv as number) ? 1 : 0;
    return dir === 'asc' ? cmp : -cmp;
  });
}

function MiniCandleChart({ bars }: { bars: OhlcvBar[] }) {
  const W = 130, H = 66, PAD = 3;
  if (bars.length === 0) {
    return (
      <div style={{ width: W, height: H, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--color-muted)', fontSize: 10 }}>
        -
      </div>
    );
  }
  const prices = bars.flatMap(b => [b.high, b.low]);
  const minP = Math.min(...prices), maxP = Math.max(...prices);
  const range = maxP - minP || 1;
  const step = (W - PAD * 2) / bars.length;
  const cw = Math.max(2, Math.floor(step * 0.65));
  const toY = (p: number) => PAD + ((maxP - p) / range) * (H - PAD * 2);
  return (
    <svg width={W} height={H} style={{ display: 'block' }}>
      {bars.map((b, i) => {
        const cx = PAD + (i + 0.5) * step;
        const isUp = b.close >= b.open;
        const color = isUp ? '#f85149' : '#388bfd';
        const bodyTop = toY(Math.max(b.open, b.close));
        const bodyH = Math.max(1, toY(Math.min(b.open, b.close)) - bodyTop);
        return (
          <g key={i}>
            <line x1={cx} y1={toY(b.high)} x2={cx} y2={toY(b.low)} stroke={color} strokeWidth={1} />
            <rect x={cx - cw / 2} y={bodyTop} width={cw} height={bodyH} fill={color} />
          </g>
        );
      })}
    </svg>
  );
}

function PnlCell({ value }: { value?: number }) {
  if (value == null) return <td style={{ padding: '6px 12px', textAlign: 'right', color: 'var(--color-muted)' }}>-</td>;
  const color = value > 0 ? 'var(--color-up)' : value < 0 ? 'var(--color-down)' : 'var(--color-muted)';
  return <td style={{ padding: '6px 12px', textAlign: 'right', color, fontFamily: 'monospace', fontWeight: 700 }}>{value > 0 ? '+' : ''}{value.toLocaleString('ko-KR')}</td>;
}

function AmountCell({ value, highlight }: { value?: number; highlight?: boolean }) {
  if (value == null || value === 0) return <td style={{ padding: '6px 12px', textAlign: 'right', color: 'var(--color-muted)' }}>-</td>;
  return <td style={{ padding: '6px 12px', textAlign: 'right', fontFamily: 'monospace', color: highlight ? 'var(--color-text)' : 'var(--color-muted)' }}>{value.toLocaleString('ko-KR')}</td>;
}

const CHART_CARD_W = 150;

function navigateToTicker(ticker: string, name = '') {
  document.cookie = `st_ticker=${encodeURIComponent(ticker)}; path=/; max-age=2592000`;
  try {
    localStorage.setItem('st_ticker', ticker);
    if (name) localStorage.setItem('st_name', name);
  } catch { /* ignore */ }
  window.location.assign('/');
}

export default function PortfolioPage() {
  const [account, setAccount] = useState('default');
  const [inputAccount, setInputAccount] = useState('default');
  const [portfolio, setPortfolio] = useState<Portfolio | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState('');
  const [chartData, setChartData] = useState<Record<string, OhlcvBar[]>>({});
  const scrollRef = useRef<HTMLDivElement>(null);
  const [canLeft, setCanLeft] = useState(false);
  const [canRight, setCanRight] = useState(false);

  function updateArrows() {
    const el = scrollRef.current;
    if (!el) return;
    setCanLeft(el.scrollLeft > 2);
    setCanRight(el.scrollLeft + el.clientWidth < el.scrollWidth - 2);
  }

  function scrollBy(delta: number) {
    scrollRef.current?.scrollBy({ left: delta, behavior: 'smooth' });
    setTimeout(updateArrows, 350);
  }

  useEffect(() => { setTimeout(updateArrows, 150); }, [chartData]);

  async function fetchCharts(tickers: string[]) {
    const results: Record<string, OhlcvBar[]> = {};
    await Promise.allSettled(
      tickers.map(async ticker => {
        try {
          const r = await fetch(`${BFF}/api/candles/${ticker}?days=30`, { signal: AbortSignal.timeout(3000) });
          if (r.ok) {
            const data = await r.json();
            const bars: OhlcvBar[] = Array.isArray(data) ? data : (data?.bars ?? data?.candles ?? data?.ohlcv ?? data?.data ?? []);
            results[ticker] = bars.slice(-30);
          }
        } catch { /* chart stays empty */ }
      })
    );
    setChartData(prev => ({ ...prev, ...results }));
  }

  async function load(acc: string) {
    setLoading(true); setErr('');
    try {
      const r = await fetch(`${BFF}/api/portfolio?account=${encodeURIComponent(acc)}`);
      if (!r.ok) throw new Error(`${r.status}: ${await r.text().then(t => t.slice(0, 120))}`);
      const data = await r.json();
      const positions: Position[] = Array.isArray(data?.positions)
        ? data.positions
        : Array.isArray(data)
        ? data
        : [];
      setPortfolio({ account: data?.account ?? acc, cash: data?.cash, total_value: data?.total_value, positions });
      if (positions.length > 0) fetchCharts(positions.map(p => p.ticker));
    } catch (e) {
      setErr(String(e));
      setPortfolio(null);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(account); }, []);  // eslint-disable-line react-hooks/exhaustive-deps

  function handleSearch() {
    const a = inputAccount.trim() || 'default';
    setAccount(a);
    load(a);
  }

  const [sortKey, setSortKey] = useState<PortSortKey>('name');
  const [sortDir, setSortDir] = useState<SortDir>('asc');

  function handleSort(key: PortSortKey) {
    const dir: SortDir = sortKey === key && sortDir === 'asc' ? 'desc' : 'asc';
    setSortKey(key); setSortDir(dir);
  }

  const positions = portfolio?.positions ?? [];
  const sortedPositions = useMemo(() => sortPositions(positions, sortKey, sortDir), [positions, sortKey, sortDir]);
  const totalPnl = positions.reduce((s, p) => s + (p.pnl ?? 0), 0);
  const totalBuyAmount = positions.reduce((s, p) => s + (p.cost_basis ?? p.avg_price * (p.quantity ?? 0)), 0);
  const totalSellAmount = positions.reduce((s, p) => s + (p.current_price != null ? p.current_price * (p.quantity ?? 0) : 0), 0);
  const totalPnlPct = totalBuyAmount > 0 ? totalPnl / totalBuyAmount : null;

  const summaryCards: { label: string; value: string; color?: string }[] = [
    { label: '보유 종목수', value: String(positions.length) },
    { label: '총 평가손익', value: totalPnl === 0 && positions.length === 0 ? '-' : (totalPnl > 0 ? '+' : '') + totalPnl.toLocaleString('ko-KR'), color: totalPnl > 0 ? 'var(--color-up)' : totalPnl < 0 ? 'var(--color-down)' : undefined },
    ...(portfolio?.cash != null ? [{ label: '잔여예수금', value: portfolio.cash.toLocaleString('ko-KR') }] : []),
    ...(portfolio?.total_value != null ? [{ label: '총 자산(예수금+평가)', value: portfolio.total_value.toLocaleString('ko-KR') }] : []),
  ];

  const arrowBtn = (show: boolean, onClick: () => void, side: 'left' | 'right', label: string) => (
    <button
      onClick={onClick}
      aria-label={label}
      style={{
        display: show ? 'flex' : 'none', position: 'absolute', [side]: 0, top: 0, bottom: 0, zIndex: 2,
        alignItems: 'center', justifyContent: 'center', width: 28,
        background: side === 'left'
          ? 'linear-gradient(to right, var(--color-card) 55%, transparent)'
          : 'linear-gradient(to left, var(--color-card) 55%, transparent)',
        border: 'none', cursor: 'pointer', color: 'var(--color-text)', fontSize: 20,
      }}
    >{side === 'left' ? '‹' : '›'}</button>
  );

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* Title + legend */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
        <h2 style={{ margin: 0, fontSize: 20, fontWeight: 700 }}>◈ 포트폴리오</h2>
        <span style={{ padding: '2px 8px', borderRadius: 4, fontSize: 11, fontWeight: 600, backgroundColor: 'rgba(88,166,255,0.12)', color: 'var(--color-accent)' }}>Phase A</span>
        <span style={{ fontSize: 11, color: 'var(--color-muted)', marginLeft: 4 }}>
          범례:&nbsp;
          <span style={{ color: 'var(--color-up)', fontWeight: 700 }}>적색(+) 이익</span>
          &nbsp;·&nbsp;
          <span style={{ color: 'var(--color-down)', fontWeight: 700 }}>파란색(−) 손해</span>
          &nbsp;· 매수총금액 = 매수시단가×수량 · 매도총금액 = 현재가×수량
        </span>
      </div>

      {/* Account selector */}
      <div style={{ display: 'flex', gap: 8, padding: 14, backgroundColor: 'var(--color-card)', borderRadius: 8, border: '1px solid var(--color-border)', flexWrap: 'wrap', alignItems: 'flex-end' }}>
        <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 12 }}>
          계좌
          <input value={inputAccount} onChange={e => setInputAccount(e.target.value)} onKeyDown={e => e.key === 'Enter' && handleSearch()} placeholder="default" style={{ width: 120, padding: '4px 8px', borderRadius: 4, border: '1px solid var(--color-border)', backgroundColor: 'var(--color-bg)', color: 'var(--color-text)' }} />
        </label>
        <button onClick={handleSearch} disabled={loading} style={{ padding: '6px 16px', borderRadius: 6, border: 'none', backgroundColor: 'var(--color-accent)', color: '#fff', fontWeight: 600, cursor: loading ? 'wait' : 'pointer', opacity: loading ? 0.7 : 1 }}>
          {loading ? '로딩…' : '조회'}
        </button>
        {account && <span style={{ fontSize: 11, color: 'var(--color-muted)', alignSelf: 'center' }}>계좌: {account}</span>}
      </div>

      {err && (
        <div style={{ color: 'var(--color-down)', fontSize: 12 }}>
          ⚠ {err} — risk-engine(:3001) 서비스 기동 필요<br />
          <span style={{ color: 'var(--color-muted)' }}>가상체결 원장: Rust risk-engine /paper/portfolio 엔드포인트</span>
        </div>
      )}

      {/* Summary cards + candlestick chart carousel */}
      {portfolio && (
        <div style={{ display: 'flex', gap: 12, alignItems: 'stretch', flexWrap: 'wrap' }}>
          {/* Summary cards */}
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, flexShrink: 0 }}>
            {summaryCards.map(item => (
              <div key={item.label} style={{ padding: '10px 16px', backgroundColor: 'var(--color-card)', borderRadius: 6, border: '1px solid var(--color-border)', minWidth: 120 }}>
                <div style={{ fontSize: 11, color: 'var(--color-muted)', marginBottom: 4 }}>{item.label}</div>
                <div style={{ fontSize: 17, fontWeight: 700, color: item.color ?? 'var(--color-text)' }}>{item.value}</div>
              </div>
            ))}
          </div>

          {/* Mini chart carousel */}
          {positions.length > 0 && (
            <div style={{ flex: 1, minWidth: 180, position: 'relative', display: 'flex', alignItems: 'center', backgroundColor: 'var(--color-card)', borderRadius: 6, border: '1px solid var(--color-border)', overflow: 'hidden' }}>
              {arrowBtn(canLeft, () => scrollBy(-CHART_CARD_W * 2), 'left', '이전')}
              <div
                ref={scrollRef}
                onScroll={updateArrows}
                style={{ display: 'flex', gap: 10, overflowX: 'hidden', padding: '8px 32px', flex: 1, scrollBehavior: 'smooth' }}
              >
                {positions.map(p => (
                  <div key={p.ticker} style={{ flexShrink: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4, padding: '6px 8px', border: '1px solid var(--color-border)', borderRadius: 6, backgroundColor: 'var(--color-bg)' }}>
                    <div style={{ fontSize: 10, color: 'var(--color-muted)', whiteSpace: 'nowrap', maxWidth: CHART_CARD_W, overflow: 'hidden', textOverflow: 'ellipsis' }}>
                      {p.name ?? p.ticker}
                    </div>
                    <MiniCandleChart bars={chartData[p.ticker] ?? []} />
                  </div>
                ))}
              </div>
              {arrowBtn(canRight, () => scrollBy(CHART_CARD_W * 2), 'right', '다음')}
            </div>
          )}
        </div>
      )}

      {/* Positions table */}
      <div style={{ backgroundColor: 'var(--color-card)', borderRadius: 8, border: '1px solid var(--color-border)', overflow: 'hidden' }}>
        <div style={{ padding: '10px 16px', borderBottom: '1px solid var(--color-border)', fontWeight: 600, fontSize: 13 }}>
          보유 포지션
          {positions.length > 0 && <span style={{ fontSize: 11, color: 'var(--color-muted)', fontWeight: 400, marginLeft: 6 }}>{positions.length}종목</span>}
        </div>
        {positions.length === 0 ? (
          <div style={{ padding: '20px 16px', fontSize: 12, color: 'var(--color-muted)' }}>
            {loading ? '로딩 중…' : err ? '데이터 조회 실패' : '보유 포지션 없음'}
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
              <thead>
                <tr style={{ borderBottom: '2px solid var(--color-border)', color: 'var(--color-muted)' }}>
                  {PORT_COLS.map(col => (
                    <th
                      key={col.key}
                      onClick={() => handleSort(col.key)}
                      style={{
                        padding: '7px 12px',
                        textAlign: col.key === 'ticker' || col.key === 'name' ? 'left' : 'right',
                        fontWeight: 600,
                        whiteSpace: 'nowrap',
                        cursor: 'pointer',
                        userSelect: 'none',
                        color: sortKey === col.key ? 'var(--color-accent)' : 'var(--color-muted)',
                        backgroundColor: sortKey === col.key ? 'rgba(88,166,255,0.06)' : 'transparent',
                      }}
                    >
                      {col.label}
                      {sortKey === col.key ? (sortDir === 'asc' ? ' ▲' : ' ▼') : ' ⇅'}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {sortedPositions.map((p, i) => (
                  <tr key={i}
                    onClick={() => navigateToTicker(p.ticker, p.name ?? '')}
                    style={{ borderBottom: '1px solid var(--color-border)', cursor: 'pointer' }}
                    title={`${p.ticker} 클릭 → 대시보드 매수/매도`}
                    onMouseEnter={e => (e.currentTarget.style.backgroundColor = 'var(--color-hover)')}
                    onMouseLeave={e => (e.currentTarget.style.backgroundColor = '')}>
                    <td style={{ padding: '6px 12px', fontFamily: 'monospace', textAlign: 'left' }}>{p.ticker}</td>
                    <td style={{ padding: '6px 12px', textAlign: 'left' }}>{p.name ?? '-'}</td>
                    <td style={{ padding: '6px 12px', textAlign: 'right' }}>{p.quantity?.toLocaleString('ko-KR') ?? '-'}</td>
                    <td style={{ padding: '6px 12px', textAlign: 'right', fontFamily: 'monospace' }}>{p.avg_price.toLocaleString('ko-KR')}</td>
                    <AmountCell value={p.cost_basis ?? p.avg_price * (p.quantity ?? 0)} />
                    <td style={{ padding: '6px 12px', textAlign: 'right', fontFamily: 'monospace' }}>{p.current_price?.toLocaleString('ko-KR') ?? '-'}</td>
                    <AmountCell value={p.current_price != null ? p.current_price * (p.quantity ?? 0) : undefined} highlight />
                    <PnlCell value={p.pnl} />
                    <td style={{ padding: '6px 12px', textAlign: 'right', color: p.pnl_pct == null ? 'var(--color-muted)' : p.pnl_pct > 0 ? 'var(--color-up)' : p.pnl_pct < 0 ? 'var(--color-down)' : 'var(--color-muted)', fontWeight: p.pnl_pct != null ? 700 : 400 }}>
                      {p.pnl_pct != null ? `${p.pnl_pct > 0 ? '+' : ''}${(p.pnl_pct * 100).toFixed(2)}%` : '-'}
                    </td>
                    <td style={{ padding: '6px 12px', textAlign: 'right', color: 'var(--color-muted)' }}>
                      {p.weight != null ? `${(p.weight * 100).toFixed(1)}%` : '-'}
                    </td>
                  </tr>
                ))}
              </tbody>
              {positions.length > 0 && (
                <tfoot>
                  <tr style={{ borderTop: '2px solid var(--color-border)', backgroundColor: 'rgba(88,166,255,0.05)' }}>
                    <td colSpan={4} style={{ padding: '6px 12px', textAlign: 'left', fontSize: 11, fontWeight: 700, color: 'var(--color-muted)' }}>합계</td>
                    {/* 매수총금액 합계 */}
                    <td style={{ padding: '6px 12px', textAlign: 'right', fontFamily: 'monospace', fontWeight: 700, color: 'var(--color-text)' }}>
                      {totalBuyAmount > 0 ? totalBuyAmount.toLocaleString('ko-KR') : '-'}
                    </td>
                    {/* 현재가 (빈 칸) */}
                    <td />
                    {/* 매도총금액 합계 */}
                    <td style={{ padding: '6px 12px', textAlign: 'right', fontFamily: 'monospace', fontWeight: 700, color: 'var(--color-text)' }}>
                      {totalSellAmount > 0 ? totalSellAmount.toLocaleString('ko-KR') : '-'}
                    </td>
                    {/* 평가손익 합계 */}
                    <td style={{ padding: '6px 12px', textAlign: 'right', fontFamily: 'monospace', fontWeight: 700, color: totalPnl > 0 ? 'var(--color-up)' : totalPnl < 0 ? 'var(--color-down)' : 'var(--color-muted)' }}>
                      {totalPnl > 0 ? '+' : ''}{totalPnl.toLocaleString('ko-KR')}
                    </td>
                    {/* 수익률 */}
                    <td style={{ padding: '6px 12px', textAlign: 'right', fontWeight: 700, color: totalPnlPct == null ? 'var(--color-muted)' : totalPnlPct > 0 ? 'var(--color-up)' : totalPnlPct < 0 ? 'var(--color-down)' : 'var(--color-muted)' }}>
                      {totalPnlPct != null ? `${totalPnlPct > 0 ? '+' : ''}${(totalPnlPct * 100).toFixed(2)}%` : '-'}
                    </td>
                    {/* 비중 */}
                    <td style={{ padding: '6px 12px', textAlign: 'right', color: 'var(--color-muted)', fontWeight: 700 }}>100%</td>
                  </tr>
                </tfoot>
              )}
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
