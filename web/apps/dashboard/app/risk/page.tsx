'use client';
import { useEffect, useState } from 'react';
import { searchStocks } from '@/lib/stocks';

const BFF = process.env.NEXT_PUBLIC_BFF_URL ?? 'http://localhost:3002';

type Alert = {
  ticker?: string; alert_type?: string; market?: string;
  short_ratio?: number; short_volume?: number; alert_date?: string;
};
type ShortRow = { date?: string; short_volume?: number; short_ratio?: number; close?: number };

const alertColor = (type?: string) => {
  if (!type) return 'var(--color-muted)';
  const t = type.toUpperCase();
  if (t.includes('위험') || t.includes('DANGER') || t.includes('HALT')) return 'var(--color-down)';
  if (t.includes('경고') || t.includes('WARN')) return '#f0a500';
  return 'var(--color-accent)';
};

// Module-level cache — survives page navigation
let _rCacheTicker = '';
let _rCacheAlerts: Alert[] = [];
let _rCacheShortRows: ShortRow[] = [];

export default function RiskPage() {
  const [alerts, setAlerts] = useState<Alert[]>(_rCacheAlerts);
  const [shortRows, setShortRows] = useState<ShortRow[]>(_rCacheShortRows);
  const [ticker, setTicker] = useState(_rCacheTicker || '005930');
  const [stockName, setStockName] = useState('');
  const [inputTicker, setInputTicker] = useState(_rCacheTicker || '005930');
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState('');

  async function resolveName(t: string): Promise<string> {
    const local = searchStocks(t, 1).find(s => s.ticker === t);
    if (local) return local.name;
    try {
      const r = await fetch(`${BFF}/api/stocks/${t}`, { signal: AbortSignal.timeout(2000) });
      if (r.ok) { const d = await r.json(); if (d?.name) return d.name as string; }
    } catch { /* ignore */ }
    return '';
  }

  // 대시보드에서 선택한 종목을 기본값으로 사용
  useEffect(() => {
    const saved = localStorage.getItem('st_ticker') ?? '005930';
    const savedName = localStorage.getItem('st_name') ?? '';
    setTicker(saved);
    setInputTicker(saved);
    const local = searchStocks(saved, 1).find(s => s.ticker === saved);
    const name = local?.name ?? savedName;
    setStockName(name);
    if (!name) resolveName(saved).then(n => { if (n) setStockName(n); });
    // 종목코드 동일하고 캐시 있으면 복원, 다르면 재조회
    if (_rCacheTicker === saved && (_rCacheAlerts.length > 0 || _rCacheShortRows.length > 0)) {
      setAlerts(_rCacheAlerts);
      setShortRows(_rCacheShortRows);
    } else {
      load(saved);
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  async function load(t: string) {
    setLoading(true); setErr('');
    try {
      const [alertsRes, shortRes] = await Promise.allSettled([
        fetch(`${BFF}/api/market-alerts?ticker=${encodeURIComponent(t)}`).then(r => r.json()),
        fetch(`${BFF}/api/short-selling/${encodeURIComponent(t)}`).then(r => r.json()),
      ]);
      const newAlerts = alertsRes.status === 'fulfilled'
        ? (Array.isArray(alertsRes.value) ? alertsRes.value : (alertsRes.value?.alerts ?? alertsRes.value?.data ?? []))
        : [];
      const newShortRows = shortRes.status === 'fulfilled'
        ? (Array.isArray(shortRes.value) ? shortRes.value : (shortRes.value?.rows ?? shortRes.value?.data ?? []))
        : [];
      _rCacheTicker = t;
      _rCacheAlerts = newAlerts;
      _rCacheShortRows = newShortRows;
      setAlerts(newAlerts);
      setShortRows(newShortRows);
    } catch (e) {
      setErr(String(e));
    } finally {
      setLoading(false);
    }
  }

  function handleSearch() {
    const t = inputTicker.trim().toUpperCase();
    if (!t) return;
    setTicker(t);
    const local = searchStocks(t, 1).find(s => s.ticker === t);
    setStockName(local?.name ?? '');
    if (!local) resolveName(t).then(n => { if (n) setStockName(n); });
    load(t);
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <h2 style={{ margin: 0, fontSize: 20, fontWeight: 700 }}>⚠ 리스크 모니터</h2>
        <span style={{ padding: '2px 8px', borderRadius: 4, fontSize: 11, fontWeight: 600, backgroundColor: 'rgba(88,166,255,0.12)', color: 'var(--color-accent)' }}>Phase B</span>
      </div>

      {/* Search bar */}
      <div style={{ display: 'flex', gap: 8, padding: 14, backgroundColor: 'var(--color-card)', borderRadius: 8, border: '1px solid var(--color-border)', flexWrap: 'wrap', alignItems: 'flex-end' }}>
        <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 12 }}>
          종목코드
          <input value={inputTicker} onChange={e => setInputTicker(e.target.value)} onKeyDown={e => e.key === 'Enter' && handleSearch()} placeholder="005930" style={{ width: 100, padding: '4px 8px', borderRadius: 4, border: '1px solid var(--color-border)', backgroundColor: 'var(--color-bg)', color: 'var(--color-text)', fontFamily: 'monospace' }} />
        </label>
        <button onClick={handleSearch} disabled={loading} style={{ padding: '6px 16px', borderRadius: 6, border: 'none', backgroundColor: 'var(--color-accent)', color: '#fff', fontWeight: 600, cursor: loading ? 'wait' : 'pointer', opacity: loading ? 0.7 : 1 }}>
          {loading ? '로딩…' : '조회'}
        </button>
        {ticker && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, alignSelf: 'center' }}>
            <span style={{ fontSize: 13, fontWeight: 700, fontFamily: 'monospace', color: 'var(--color-text)' }}>{ticker}</span>
            {stockName && <span style={{ fontSize: 13, color: 'var(--color-muted)' }}>{stockName}</span>}
          </div>
        )}
      </div>

      {err && <div style={{ color: 'var(--color-down)', fontSize: 12 }}>⚠ {err} — ingest(:8003) 서비스 기동 필요</div>}

      {/* Market alerts */}
      <div style={{ backgroundColor: 'var(--color-card)', borderRadius: 8, border: '1px solid var(--color-border)', overflow: 'hidden' }}>
        <div style={{ padding: '10px 16px', borderBottom: '1px solid var(--color-border)', fontWeight: 600, fontSize: 13 }}>
          시장경보 {alerts.length > 0 && <span style={{ fontSize: 11, color: 'var(--color-muted)', fontWeight: 400, marginLeft: 6 }}>{alerts.length}건</span>}
        </div>
        {alerts.length === 0 ? (
          <div style={{ padding: '20px 16px', fontSize: 12, color: 'var(--color-muted)' }}>
            {loading ? '로딩 중…' : '경보 없음 (조회 기준 정상)'}
          </div>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--color-border)', color: 'var(--color-muted)' }}>
                {['종목', '경보유형', '마켓', '공매도비율', '날짜'].map(h => (
                  <th key={h} style={{ padding: '6px 12px', textAlign: 'left', fontWeight: 600 }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {alerts.map((a, i) => (
                <tr key={i} style={{ borderBottom: '1px solid var(--color-border)' }}>
                  <td style={{ padding: '6px 12px', fontFamily: 'monospace' }}>{a.ticker ?? '-'}</td>
                  <td style={{ padding: '6px 12px' }}>
                    <span style={{ color: alertColor(a.alert_type), fontWeight: 600 }}>{a.alert_type ?? '-'}</span>
                  </td>
                  <td style={{ padding: '6px 12px', color: 'var(--color-muted)' }}>{a.market ?? '-'}</td>
                  <td style={{ padding: '6px 12px' }}>{a.short_ratio != null ? (a.short_ratio * 100).toFixed(2) + '%' : '-'}</td>
                  <td style={{ padding: '6px 12px', color: 'var(--color-muted)' }}>{a.alert_date ?? '-'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Short selling trend */}
      <div style={{ backgroundColor: 'var(--color-card)', borderRadius: 8, border: '1px solid var(--color-border)', overflow: 'hidden' }}>
        <div style={{ padding: '10px 16px', borderBottom: '1px solid var(--color-border)', fontWeight: 600, fontSize: 13 }}>
          공매도 추이
          <span style={{ fontSize: 11, color: 'var(--color-muted)', fontWeight: 400, marginLeft: 6 }}>
            {ticker}{stockName ? ` · ${stockName}` : ''}{shortRows.length > 0 ? ` · ${shortRows.length}일` : ''}
          </span>
        </div>
        {shortRows.length === 0 ? (
          <div style={{ padding: '20px 16px', fontSize: 12, color: 'var(--color-muted)' }}>
            {loading ? '로딩 중…' : '공매도 데이터 없음'}
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--color-border)', color: 'var(--color-muted)' }}>
                  {['날짜', '공매도수량', '공매도비율', '종가'].map(h => (
                    <th key={h} style={{ padding: '6px 12px', textAlign: 'right', fontWeight: 600 }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {shortRows.slice(0, 30).map((row, i) => (
                  <tr key={i} style={{ borderBottom: '1px solid var(--color-border)' }}>
                    <td style={{ padding: '6px 12px', color: 'var(--color-muted)' }}>{row.date ?? '-'}</td>
                    <td style={{ padding: '6px 12px', textAlign: 'right' }}>{row.short_volume?.toLocaleString('ko-KR') ?? '-'}</td>
                    <td style={{ padding: '6px 12px', textAlign: 'right', color: (row.short_ratio ?? 0) > 0.2 ? 'var(--color-down)' : (row.short_ratio ?? 0) > 0.1 ? '#f0a500' : 'var(--color-text)' }}>
                      {row.short_ratio != null ? (row.short_ratio * 100).toFixed(2) + '%' : '-'}
                    </td>
                    <td style={{ padding: '6px 12px', textAlign: 'right', fontFamily: 'monospace' }}>{row.close?.toLocaleString('ko-KR') ?? '-'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
