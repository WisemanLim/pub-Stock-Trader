'use client';
import { useEffect, useState } from 'react';
import { searchStocks } from '@/lib/stocks';

const BFF = process.env.NEXT_PUBLIC_BFF_URL ?? 'http://localhost:3002';

const PERSONAS = ['swing', 'scalp', 'position', 'safe'];

type AgentNote = { agent_name: string; summary: string; data: Record<string, unknown> };
type Decision = { signal: string; confidence: number; weight: number; rationale: string };
type AnalyzeResult = { ticker: string; persona: string; notes: AgentNote[]; decision: Decision };

const signalColor = (s: string) =>
  s === 'BUY' ? 'var(--color-up)' : s === 'SELL' ? 'var(--color-down)' : 'var(--color-muted)';
const signalBg = (s: string) =>
  s === 'BUY' ? 'rgba(63,185,80,0.12)' : s === 'SELL' ? 'rgba(248,81,73,0.12)' : 'rgba(110,118,129,0.1)';

// Module-level cache — survives page navigation
let _agCacheTicker = '';
let _agCacheResult: AnalyzeResult | null = null;
let _agCachePersona = 'swing';

export default function AgentsPage() {
  const [ticker, setTicker] = useState(_agCacheTicker || '005930');
  const [stockName, setStockName] = useState('');
  const [persona, setPersona] = useState(_agCachePersona);
  const [result, setResult] = useState<AnalyzeResult | null>(_agCacheResult);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState('');

  // 대시보드 선택 종목 기본값
  useEffect(() => {
    const saved = localStorage.getItem('st_ticker') ?? '005930';
    const savedName = localStorage.getItem('st_name') ?? '';
    const local = searchStocks(saved, 1).find(s => s.ticker === saved);
    const name = local?.name ?? savedName;
    setStockName(name);
    if (!name) {
      fetch(`${BFF}/api/stocks/${saved}`, { signal: AbortSignal.timeout(2000) })
        .then(r => r.ok ? r.json() : null)
        .then(d => { if (d?.name) setStockName(d.name as string); })
        .catch(() => {});
    }
    // 종목코드 동일하고 캐시 있으면 복원, 다르면 재실행
    if (_agCacheTicker === saved && _agCacheResult) {
      setTicker(saved);
      setResult(_agCacheResult);
    } else {
      setTicker(saved);
      runAnalyze(saved, persona);
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  async function runAnalyze(tickerOvr?: string, personaOvr?: string) {
    const t = (tickerOvr ?? ticker).trim().toUpperCase();
    const p = personaOvr ?? persona;
    setLoading(true); setErr(''); setResult(null);
    try {
      const r = await fetch(`${BFF}/api/agents/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ticker: t, persona: p }),
      });
      if (!r.ok) {
        const text = await r.text();
        throw new Error(`${r.status}: ${text.slice(0, 120)}`);
      }
      const data = await r.json();
      _agCacheTicker = t;
      _agCacheResult = data;
      setResult(data);
    } catch (e) {
      setErr(String(e));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <h2 style={{ margin: 0, fontSize: 20, fontWeight: 700 }}>◉ 에이전트 분석</h2>
        <span style={{ padding: '2px 8px', borderRadius: 4, fontSize: 11, fontWeight: 600, backgroundColor: 'rgba(88,166,255,0.12)', color: 'var(--color-accent)' }}>Phase C</span>
      </div>

      {/* Input */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, padding: 16, backgroundColor: 'var(--color-card)', borderRadius: 8, border: '1px solid var(--color-border)' }}>
        <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 12 }}>
          종목코드
          <input value={ticker} onChange={e => { setTicker(e.target.value.toUpperCase()); setStockName(''); }} placeholder="005930" style={{ width: 100, padding: '4px 8px', borderRadius: 4, border: '1px solid var(--color-border)', backgroundColor: 'var(--color-bg)', color: 'var(--color-text)', fontFamily: 'monospace' }} />
        </label>
        {stockName && (
          <div style={{ display: 'flex', alignItems: 'flex-end', paddingBottom: 4 }}>
            <span style={{ fontSize: 14, fontWeight: 600, color: 'var(--color-text)' }}>{stockName}</span>
          </div>
        )}
        <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 12 }}>
          페르소나
          <select value={persona} onChange={e => setPersona(e.target.value)} style={{ padding: '4px 8px', borderRadius: 4, border: '1px solid var(--color-border)', backgroundColor: 'var(--color-bg)', color: 'var(--color-text)' }}>
            {PERSONAS.map(p => <option key={p} value={p}>{p}</option>)}
          </select>
        </label>
        <div style={{ display: 'flex', alignItems: 'flex-end' }}>
          <button onClick={() => runAnalyze()} disabled={loading} style={{ padding: '6px 20px', borderRadius: 6, border: 'none', backgroundColor: 'var(--color-accent)', color: '#fff', fontWeight: 600, cursor: loading ? 'wait' : 'pointer', opacity: loading ? 0.7 : 1 }}>
            {loading ? '분석 중…' : '에이전트 실행'}
          </button>
        </div>
      </div>

      {err && <div style={{ color: 'var(--color-down)', fontSize: 12 }}>⚠ {err} — agents(:8004) 서비스 기동 필요</div>}

      {result && (
        <>
          {/* Decision */}
          <div style={{ padding: 20, backgroundColor: 'var(--color-card)', borderRadius: 8, border: `1px solid ${signalColor(result.decision.signal)}33`, display: 'flex', gap: 24, flexWrap: 'wrap', alignItems: 'center' }}>
            <div>
              <div style={{ fontSize: 11, color: 'var(--color-muted)', marginBottom: 4 }}>최종 시그널</div>
              <div style={{ fontSize: 28, fontWeight: 800, color: signalColor(result.decision.signal), backgroundColor: signalBg(result.decision.signal), padding: '4px 16px', borderRadius: 6 }}>{result.decision.signal}</div>
            </div>
            <div>
              <div style={{ fontSize: 11, color: 'var(--color-muted)', marginBottom: 4 }}>신뢰도</div>
              <div style={{ fontSize: 22, fontWeight: 700 }}>{(result.decision.confidence * 100).toFixed(0)}%</div>
            </div>
            <div>
              <div style={{ fontSize: 11, color: 'var(--color-muted)', marginBottom: 4 }}>포지션 비중</div>
              <div style={{ fontSize: 22, fontWeight: 700 }}>{(result.decision.weight * 100).toFixed(0)}%</div>
            </div>
            <div style={{ flex: 1, minWidth: 200 }}>
              <div style={{ fontSize: 11, color: 'var(--color-muted)', marginBottom: 4 }}>근거</div>
              <div style={{ fontSize: 13, lineHeight: 1.5 }}>{result.decision.rationale}</div>
            </div>
          </div>

          {/* Agent pipeline notes */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            <div style={{ fontSize: 12, color: 'var(--color-muted)', fontWeight: 600 }}>에이전트 파이프라인 ({result.notes.length}개)</div>
            {result.notes.map((note, i) => (
              <div key={i} style={{ padding: '10px 14px', backgroundColor: 'var(--color-card)', borderRadius: 6, border: '1px solid var(--color-border)' }}>
                <div style={{ display: 'flex', gap: 8, marginBottom: 4, alignItems: 'center' }}>
                  <span style={{ fontSize: 10, fontWeight: 700, color: 'var(--color-accent)', backgroundColor: 'rgba(88,166,255,0.1)', padding: '1px 6px', borderRadius: 3 }}>
                    {String(i + 1).padStart(2, '0')} {note.agent_name}
                  </span>
                </div>
                <div style={{ fontSize: 12, color: 'var(--color-text)' }}>{note.summary}</div>
                {Object.keys(note.data).length > 0 && (
                  <details style={{ marginTop: 6 }}>
                    <summary style={{ fontSize: 11, color: 'var(--color-muted)', cursor: 'pointer' }}>데이터 보기</summary>
                    <pre style={{ fontSize: 10, color: 'var(--color-muted)', marginTop: 4, overflow: 'auto', maxHeight: 120 }}>{JSON.stringify(note.data, null, 2)}</pre>
                  </details>
                )}
              </div>
            ))}
          </div>
        </>
      )}

      {!loading && !result && !err && (
        <div style={{ color: 'var(--color-muted)', fontSize: 13, padding: 24, textAlign: 'center' }}>
          종목코드와 페르소나를 선택 후 &ldquo;에이전트 실행&rdquo; 버튼을 누르세요.<br />
          <span style={{ fontSize: 11 }}>Scraper → Analyst → Portfolio → FlowAgent → AlertAgent → Decision</span>
        </div>
      )}
    </div>
  );
}
