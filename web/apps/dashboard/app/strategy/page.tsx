'use client';
import { useState, useMemo } from 'react';
import { useRouter } from 'next/navigation';

const BFF = process.env.NEXT_PUBLIC_BFF_URL ?? 'http://localhost:3002';

function navigateToTicker(ticker: string, name = '') {
  document.cookie = `st_ticker=${encodeURIComponent(ticker)}; path=/; max-age=2592000`;
  try {
    localStorage.setItem('st_ticker', ticker);
    if (name) localStorage.setItem('st_name', name);
  } catch { /* ignore */ }
  window.location.assign('/');
}

// ─── 스크리너 타입 ───────────────────────────────────────────────────────────
type ScreenerRow = {
  ticker: string; name: string; close: number; volume: number;
  rsi: number | null; signal: string; short_ratio: number | null; esg_score: number | null;
};
type SortKey = keyof ScreenerRow;
type SortDir = 'asc' | 'desc';

const signalStyle = (s: string): React.CSSProperties => ({
  padding: '2px 8px', borderRadius: 4, fontSize: 11, fontWeight: 600,
  backgroundColor: s === 'BUY' ? 'rgba(63,185,80,0.15)' : s === 'SELL' ? 'rgba(248,81,73,0.15)' : 'rgba(110,118,129,0.15)',
  color: s === 'BUY' ? 'var(--color-up)' : s === 'SELL' ? 'var(--color-down)' : 'var(--color-muted)',
});

function compareRows(a: ScreenerRow, b: ScreenerRow, key: SortKey, dir: SortDir): number {
  const av = a[key], bv = b[key];
  if (av == null && bv == null) return 0;
  if (av == null) return 1;
  if (bv == null) return -1;
  const cmp = typeof av === 'string' && typeof bv === 'string'
    ? av.localeCompare(bv, 'ko')
    : (av as number) < (bv as number) ? -1 : (av as number) > (bv as number) ? 1 : 0;
  return dir === 'asc' ? cmp : -cmp;
}

// ─── 모듈 캐시 ───────────────────────────────────────────────────────────────
let _market = 'KRX', _signal = '', _minEsg = '', _maxShort = '';
let _rsiMin = '', _rsiMax = '', _minVol = '', _minClose = '', _maxClose = '';
let _limit = 20;
let _results: ScreenerRow[] = [];
let _meta: { total_scanned: number; matched: number } | null = null;
let _sortKey: SortKey = 'name', _sortDir: SortDir = 'desc';

const COLUMNS: { key: SortKey; label: string; align: 'left' | 'right' }[] = [
  { key: 'ticker',      label: '종목코드', align: 'left'  },
  { key: 'name',        label: '종목명',   align: 'left'  },
  { key: 'close',       label: '현재가',   align: 'right' },
  { key: 'volume',      label: '거래량',   align: 'right' },
  { key: 'rsi',         label: 'RSI',      align: 'right' },
  { key: 'signal',      label: '시그널',   align: 'right' },
  { key: 'esg_score',   label: 'ESG',      align: 'right' },
  { key: 'short_ratio', label: '공매도%',  align: 'right' },
];

// ─── 메인 페이지 ─────────────────────────────────────────────────────────────
export default function StrategyPage() {
  const router = useRouter();

  const [market,   setMarket]   = useState(_market);
  const [signal,   setSignal]   = useState(_signal);
  const [minEsg,   setMinEsg]   = useState(_minEsg);
  const [maxShort, setMaxShort] = useState(_maxShort);
  const [rsiMin,   setRsiMin]   = useState(_rsiMin);
  const [rsiMax,   setRsiMax]   = useState(_rsiMax);
  const [minVol,   setMinVol]   = useState(_minVol);
  const [minClose, setMinClose] = useState(_minClose);
  const [maxClose, setMaxClose] = useState(_maxClose);
  const [limit,    setLimit]    = useState(_limit);
  const [results,  setResults]  = useState<ScreenerRow[]>(_results);
  const [meta,     setMeta]     = useState(_meta);
  const [loading,  setLoading]  = useState(false);
  const [err,      setErr]      = useState('');
  const [sortKey,  setSortKey]  = useState<SortKey>(_sortKey);
  const [sortDir,  setSortDir]  = useState<SortDir>(_sortDir);

  const sortedResults = useMemo(
    () => [...results].sort((a, b) => compareRows(a, b, sortKey, sortDir)),
    [results, sortKey, sortDir],
  );

  function handleSort(key: SortKey) {
    const dir: SortDir = sortKey === key ? (sortDir === 'asc' ? 'desc' : 'asc') : 'asc';
    _sortKey = key; _sortDir = dir;
    setSortKey(key); setSortDir(dir);
  }

  async function runScreener() {
    setLoading(true); setErr('');
    try {
      const body: Record<string, unknown> = { market, limit };
      if (signal)   body.signal = signal;
      if (minEsg)   body.min_esg_score = parseFloat(minEsg);
      if (maxShort) body.max_short_ratio = parseFloat(maxShort) / 100;
      if (rsiMin)   body.rsi_min = parseFloat(rsiMin);
      if (rsiMax)   body.rsi_max = parseFloat(rsiMax);
      if (minVol)   body.min_volume = parseInt(minVol);
      if (minClose) body.min_close = parseFloat(minClose);
      if (maxClose) body.max_close = parseFloat(maxClose);
      const r = await fetch(`${BFF}/api/screener`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (!r.ok) throw new Error(`BFF ${r.status}`);
      const data = await r.json();
      const newResults: ScreenerRow[] = data.results ?? [];
      const newMeta = { total_scanned: data.total_scanned, matched: data.matched };
      _results = newResults; _meta = newMeta;
      setResults(newResults); setMeta(newMeta);
    } catch (e) {
      setErr(String(e));
    } finally {
      setLoading(false);
    }
  }

  const inp: React.CSSProperties = {
    padding: '4px 8px', borderRadius: 4,
    border: '1px solid var(--color-border)',
    backgroundColor: 'var(--color-bg)', color: 'var(--color-text)',
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* 헤더 */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <h2 style={{ margin: 0, fontSize: 20, fontWeight: 700 }}>◎ 전략 · 스크리너</h2>
        <span style={{ padding: '2px 8px', borderRadius: 4, fontSize: 11, fontWeight: 600, backgroundColor: 'rgba(88,166,255,0.12)', color: 'var(--color-accent)' }}>Phase C+D</span>
      </div>

      {/* 백테스팅 링크 배너 */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '10px 16px', backgroundColor: 'rgba(88,166,255,0.06)', borderRadius: 8, border: '1px solid rgba(88,166,255,0.2)' }}>
        <span style={{ fontSize: 12, color: 'var(--color-muted)' }}>
          스크리닝 결과 종목의 전략 백테스트(규칙기반·강화학습)는 백테스팅 페이지에서 실행합니다.
        </span>
        <button
          onClick={() => router.push('/backtest')}
          style={{ marginLeft: 'auto', padding: '5px 14px', borderRadius: 6, border: 'none', backgroundColor: 'var(--color-accent)', color: '#fff', fontWeight: 600, fontSize: 12, cursor: 'pointer', whiteSpace: 'nowrap' }}
        >
          ↺ 백테스팅 →
        </button>
      </div>

      {/* 필터 바 */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, padding: 16, backgroundColor: 'var(--color-card)', borderRadius: 8, border: '1px solid var(--color-border)' }}>
        <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 12 }}>
          마켓
          <select value={market} onChange={e => { _market = e.target.value; setMarket(e.target.value); }} style={inp}>
            <option value="KRX">KRX</option>
            <option value="KOSPI">KOSPI</option>
            <option value="KOSDAQ">KOSDAQ</option>
          </select>
        </label>
        <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 12 }}>
          시그널
          <select value={signal} onChange={e => { _signal = e.target.value; setSignal(e.target.value); }} style={inp}>
            <option value="">전체</option>
            <option value="BUY">BUY</option>
            <option value="SELL">SELL</option>
            <option value="HOLD">HOLD</option>
          </select>
        </label>
        <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 12 }}>
          RSI 최소
          <input type="number" value={rsiMin} onChange={e => { _rsiMin = e.target.value; setRsiMin(e.target.value); }} placeholder="예: 20" min={0} max={100} style={{ ...inp, width: 80 }} />
        </label>
        <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 12 }}>
          RSI 최대
          <input type="number" value={rsiMax} onChange={e => { _rsiMax = e.target.value; setRsiMax(e.target.value); }} placeholder="예: 70" min={0} max={100} style={{ ...inp, width: 80 }} />
        </label>
        <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 12 }}>
          최소 거래량
          <input type="number" value={minVol} onChange={e => { _minVol = e.target.value; setMinVol(e.target.value); }} placeholder="예: 100000" min={0} style={{ ...inp, width: 110 }} />
        </label>
        <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 12 }}>
          종가 하한 (원)
          <input type="number" value={minClose} onChange={e => { _minClose = e.target.value; setMinClose(e.target.value); }} placeholder="예: 5000" min={0} style={{ ...inp, width: 110 }} />
        </label>
        <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 12 }}>
          종가 상한 (원)
          <input type="number" value={maxClose} onChange={e => { _maxClose = e.target.value; setMaxClose(e.target.value); }} placeholder="예: 100000" min={0} style={{ ...inp, width: 110 }} />
        </label>
        <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 12 }}>
          최소 ESG 점수
          <input type="number" value={minEsg} onChange={e => { _minEsg = e.target.value; setMinEsg(e.target.value); }} placeholder="예: 40" min={0} max={100} style={{ ...inp, width: 90 }} />
        </label>
        <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 12 }}>
          최대 공매도 (%)
          <input type="number" value={maxShort} onChange={e => { _maxShort = e.target.value; setMaxShort(e.target.value); }} placeholder="예: 10" min={0} max={100} style={{ ...inp, width: 90 }} />
        </label>
        <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 12 }}>
          결과 수
          <input type="number" value={limit} onChange={e => { const v = parseInt(e.target.value) || 20; _limit = v; setLimit(v); }} min={5} max={80} style={{ ...inp, width: 70 }} />
        </label>
        <div style={{ display: 'flex', alignItems: 'flex-end' }}>
          <button onClick={runScreener} disabled={loading}
            style={{ padding: '6px 20px', borderRadius: 6, border: 'none', backgroundColor: 'var(--color-accent)', color: '#fff', fontWeight: 600, cursor: loading ? 'wait' : 'pointer', opacity: loading ? 0.7 : 1 }}>
            {loading ? '검색 중…' : '스크리닝'}
          </button>
        </div>
      </div>

      {err && <div style={{ color: 'var(--color-down)', fontSize: 12 }}>⚠ {err} — BFF(:3002) / analysis(:8001) 서비스 기동 필요</div>}

      {meta && (
        <div style={{ fontSize: 12, color: 'var(--color-muted)' }}>
          스캔 {meta.total_scanned}종목 · 매칭 <strong style={{ color: 'var(--color-text)' }}>{meta.matched}</strong>종목
          <span style={{ marginLeft: 12 }}>정렬: {COLUMNS.find(c => c.key === sortKey)?.label} {sortDir === 'asc' ? '▲' : '▼'}</span>
        </div>
      )}

      {results.length > 0 && (
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
            <thead>
              <tr style={{ borderBottom: '2px solid var(--color-border)', color: 'var(--color-muted)' }}>
                {COLUMNS.map(col => (
                  <th key={col.key} onClick={() => handleSort(col.key)}
                    style={{ padding: '7px 10px', textAlign: col.align, fontWeight: 600, whiteSpace: 'nowrap', cursor: 'pointer', userSelect: 'none', color: sortKey === col.key ? 'var(--color-accent)' : 'var(--color-muted)', backgroundColor: sortKey === col.key ? 'rgba(88,166,255,0.06)' : 'transparent' }}>
                    {col.label}{sortKey === col.key ? (sortDir === 'asc' ? ' ▲' : ' ▼') : ' ⇅'}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {sortedResults.map((r, i) => (
                <tr key={i}
                  onClick={() => navigateToTicker(r.ticker, r.name ?? '')}
                  style={{ borderBottom: '1px solid var(--color-border)', cursor: 'pointer' }}
                  title={`${r.ticker} 클릭 → 대시보드 매수/매도`}
                  onMouseEnter={e => (e.currentTarget.style.backgroundColor = 'var(--color-hover)')}
                  onMouseLeave={e => (e.currentTarget.style.backgroundColor = '')}>
                  <td style={{ padding: '6px 10px', fontFamily: 'monospace' }}>{r.ticker}</td>
                  <td style={{ padding: '6px 10px' }}>{r.name ?? '-'}</td>
                  <td style={{ padding: '6px 10px', textAlign: 'right', fontFamily: 'monospace' }}>{r.close.toLocaleString('ko-KR')}</td>
                  <td style={{ padding: '6px 10px', textAlign: 'right', color: 'var(--color-muted)' }}>{r.volume.toLocaleString('ko-KR')}</td>
                  <td style={{ padding: '6px 10px', textAlign: 'right', color: r.rsi == null ? 'var(--color-muted)' : r.rsi < 30 ? 'var(--color-up)' : r.rsi > 70 ? 'var(--color-down)' : 'var(--color-text)' }}>{r.rsi ?? '-'}</td>
                  <td style={{ padding: '6px 10px', textAlign: 'right' }}><span style={signalStyle(r.signal)}>{r.signal}</span></td>
                  <td style={{ padding: '6px 10px', textAlign: 'right', color: r.esg_score == null ? 'var(--color-muted)' : r.esg_score >= 70 ? 'var(--color-up)' : r.esg_score >= 50 ? '#f0a500' : 'var(--color-down)' }}>{r.esg_score != null ? r.esg_score.toFixed(1) : '-'}</td>
                  <td style={{ padding: '6px 10px', textAlign: 'right', color: r.short_ratio == null ? 'var(--color-muted)' : r.short_ratio > 0.2 ? 'var(--color-down)' : r.short_ratio > 0.1 ? '#f0a500' : 'var(--color-text)' }}>{r.short_ratio != null ? (r.short_ratio * 100).toFixed(2) + '%' : '-'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {!loading && results.length === 0 && !err && (
        <div style={{ color: 'var(--color-muted)', fontSize: 13, padding: 24, textAlign: 'center' }}>
          조건을 설정하고 &ldquo;스크리닝&rdquo; 버튼을 누르세요.
        </div>
      )}
    </div>
  );
}
