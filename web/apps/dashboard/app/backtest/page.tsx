'use client';
import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { searchStocks } from '@/lib/stocks';

const BFF = process.env.NEXT_PUBLIC_BFF_URL ?? 'http://localhost:3002';

// ─── 타입 ────────────────────────────────────────────────────────────────────
// analysis 서비스 raw 응답 — flat, _pct 필드는 이미 ×100
type BacktestRaw = {
  ticker: string; strategy: string; bars: number;
  total_return_pct: number; max_drawdown_pct: number;
  sharpe: number; sortino?: number; win_rate: number;
  profit_factor?: number; num_trades: number;
  initial_capital: number; final_equity: number;
  episodes?: number;
  trades?: unknown[];
};
type Metrics = {
  total_return: number; sharpe?: number;
  max_drawdown: number; win_rate: number; total_trades: number;
};
type BacktestResult = {
  ticker: string; strategy: string; days: number;
  metrics: Metrics; trades?: unknown[];
};

function mapRaw(raw: BacktestRaw, days: number): BacktestResult {
  return {
    ticker:   raw.ticker,
    strategy: raw.strategy,
    days,
    metrics: {
      total_return: raw.total_return_pct / 100,
      max_drawdown: raw.max_drawdown_pct / 100,
      sharpe:       raw.sharpe,
      win_rate:     raw.win_rate,
      total_trades: raw.num_trades,
    },
    trades: raw.trades,
  };
}

// ─── 모듈 캐시 (규칙기반만) ──────────────────────────────────────────────────
let _ruleCache: BacktestResult | null = null;
let _ruleCacheKey = '';

// ─── 공통 컴포넌트 ────────────────────────────────────────────────────────────
function MetricCard({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div style={{ padding: '12px 16px', backgroundColor: 'var(--color-bg)', borderRadius: 6, border: '1px solid var(--color-border)', minWidth: 110 }}>
      <div style={{ fontSize: 11, color: 'var(--color-muted)', marginBottom: 4 }}>{label}</div>
      <div style={{ fontSize: 18, fontWeight: 700, color: color ?? 'var(--color-text)' }}>{value}</div>
    </div>
  );
}

function MetricsPanel({ result, stockName }: { result: BacktestResult; stockName: string }) {
  const m = result.metrics;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12, marginTop: 16 }}>
      <div style={{ fontSize: 12, color: 'var(--color-muted)' }}>
        <strong style={{ color: 'var(--color-text)' }}>{result.ticker}</strong>
        {stockName && <span style={{ marginLeft: 6 }}>{stockName}</span>}
        <span style={{ marginLeft: 8, fontFamily: 'monospace' }}>
          {result.strategy} · {result.days}일
        </span>
      </div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10 }}>
        <MetricCard label="총 수익률" value={`${(m.total_return * 100).toFixed(2)}%`}
          color={m.total_return >= 0 ? 'var(--color-up)' : 'var(--color-down)'} />
        {m.sharpe !== undefined && (
          <MetricCard label="샤프 지수" value={m.sharpe.toFixed(3)}
            color={m.sharpe >= 1 ? 'var(--color-up)' : m.sharpe >= 0 ? '#f0a500' : 'var(--color-down)'} />
        )}
        <MetricCard label="최대 낙폭" value={`${(m.max_drawdown * 100).toFixed(2)}%`}
          color="var(--color-down)" />
        <MetricCard label="승률" value={`${(m.win_rate * 100).toFixed(1)}%`}
          color={m.win_rate >= 0.5 ? 'var(--color-up)' : 'var(--color-muted)'} />
        <MetricCard label="총 거래수" value={String(m.total_trades)} />
      </div>
      {result.trades && result.trades.length > 0 && (
        <details>
          <summary style={{ fontSize: 12, color: 'var(--color-muted)', cursor: 'pointer', padding: '6px 0' }}>
            거래 내역 ({result.trades.length}건)
          </summary>
          <pre style={{ fontSize: 10, color: 'var(--color-muted)', maxHeight: 240, overflow: 'auto', backgroundColor: 'var(--color-bg)', padding: 10, borderRadius: 6, border: '1px solid var(--color-border)', marginTop: 4 }}>
            {JSON.stringify(result.trades.slice(0, 20), null, 2)}
          </pre>
        </details>
      )}
    </div>
  );
}

const SEL: React.CSSProperties = {
  padding: '4px 8px', borderRadius: 4,
  border: '1px solid var(--color-border)',
  backgroundColor: 'var(--color-bg)', color: 'var(--color-text)',
};

// ─── 규칙기반 탭 ──────────────────────────────────────────────────────────────
const RULE_STRATEGIES = [
  { value: 'sma_cross',      label: 'SMA 교차' },
  { value: 'rsi_threshold',  label: 'RSI 임계값' },
  { value: 'macd_cross',     label: 'MACD 교차' },
  { value: 'qlearn',         label: 'Q-러닝' },
];

function RuleBasedTab({ ticker, stockName }: { ticker: string; stockName: string }) {
  const [strategy, setStrategy] = useState('sma_cross');
  const [days,     setDays]     = useState(365);
  const [result,   setResult]   = useState<BacktestResult | null>(null);
  const [loading,  setLoading]  = useState(false);
  const [err,      setErr]      = useState('');

  // 마운트 시 캐시 복원 또는 자동 실행
  useEffect(() => {
    const cacheKey = `${ticker}|sma_cross|365`;
    if (_ruleCacheKey === cacheKey && _ruleCache) {
      setResult(_ruleCache);
    } else if (ticker) {
      run(ticker, 'sma_cross', 365);
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  async function run(t = ticker, s = strategy, d = days) {
    setLoading(true); setErr(''); setResult(null);
    try {
      const r = await fetch(`${BFF}/api/backtest`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ticker: t.trim().toUpperCase(), strategy: s, days: d }),
      });
      if (!r.ok) throw new Error(`${r.status}: ${(await r.text()).slice(0, 160)}`);
      const raw: BacktestRaw = await r.json();
      const mapped = mapRaw(raw, d);
      _ruleCache = mapped;
      _ruleCacheKey = `${t}|${s}|${d}`;
      setResult(mapped);
    } catch (e) {
      setErr(String(e));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      <div style={{ fontSize: 13, color: 'var(--color-muted)' }}>
        SMA교차·RSI임계·MACD·Q-러닝 기반 규칙 매매 전략 시뮬레이션
      </div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, alignItems: 'flex-end' }}>
        <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 12 }}>
          전략
          <select value={strategy} onChange={e => setStrategy(e.target.value)} style={SEL}>
            {RULE_STRATEGIES.map(s => <option key={s.value} value={s.value}>{s.label}</option>)}
          </select>
        </label>
        <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 12 }}>
          기간 (일)
          <select value={days} onChange={e => setDays(parseInt(e.target.value))} style={SEL}>
            <option value={60}>60일</option>
            <option value={180}>180일</option>
            <option value={365}>365일</option>
            <option value={730}>730일</option>
          </select>
        </label>
        <button onClick={() => run()} disabled={loading}
          style={{ padding: '6px 20px', borderRadius: 6, border: 'none', backgroundColor: 'var(--color-accent)', color: '#fff', fontWeight: 600, cursor: loading ? 'wait' : 'pointer', opacity: loading ? 0.7 : 1 }}>
          {loading ? '실행 중…' : '백테스트 실행'}
        </button>
      </div>
      {err && <div style={{ color: 'var(--color-down)', fontSize: 12 }}>⚠ {err}</div>}
      {result && <MetricsPanel result={result} stockName={stockName} />}
    </div>
  );
}

// ─── 강화학습 탭 ──────────────────────────────────────────────────────────────
const RL_ALGOS = [
  { value: 'DQN',   label: 'DQN (Deep Q-Network)' },
  { value: 'PPO',   label: 'PPO (Proximal Policy Opt.)' },
  { value: 'A2C',   label: 'A2C (Advantage Actor-Critic)' },
  { value: 'QRDQN', label: 'QR-DQN (분포형 Q)' },
];

function RLTab({ ticker, stockName }: { ticker: string; stockName: string }) {
  const [algo,     setAlgo]     = useState('DQN');
  const [days,     setDays]     = useState(365);
  const [episodes, setEpisodes] = useState(50);
  const [result,   setResult]   = useState<BacktestResult | null>(null);
  const [loading,  setLoading]  = useState(false);
  const [err,      setErr]      = useState('');

  async function run() {
    setLoading(true); setErr(''); setResult(null);
    try {
      const r = await fetch(`${BFF}/api/backtest/rl`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ticker: ticker.trim().toUpperCase(), algo, days, episodes }),
      });
      if (!r.ok) throw new Error(`${r.status}: ${(await r.text()).slice(0, 160)}`);
      const raw: BacktestRaw = await r.json();
      setResult(mapRaw(raw, days));
    } catch (e) {
      setErr(String(e));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      <div style={{ fontSize: 13, color: 'var(--color-muted)' }}>
        DQN·PPO·A2C·QR-DQN 강화학습 에이전트 백테스트 — 에피소드 단위 학습 (수 분 소요)
      </div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, alignItems: 'flex-end' }}>
        <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 12 }}>
          알고리즘
          <select value={algo} onChange={e => setAlgo(e.target.value)} style={SEL}>
            {RL_ALGOS.map(a => <option key={a.value} value={a.value}>{a.label}</option>)}
          </select>
        </label>
        <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 12 }}>
          기간 (일)
          <select value={days} onChange={e => setDays(parseInt(e.target.value))} style={SEL}>
            <option value={60}>60일</option>
            <option value={180}>180일</option>
            <option value={365}>365일</option>
          </select>
        </label>
        <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 12 }}>
          에피소드
          <select value={episodes} onChange={e => setEpisodes(parseInt(e.target.value))} style={SEL}>
            <option value={30}>30</option>
            <option value={50}>50</option>
            <option value={100}>100</option>
          </select>
        </label>
        <button onClick={run} disabled={loading}
          style={{ padding: '6px 20px', borderRadius: 6, border: 'none', backgroundColor: 'var(--color-accent)', color: '#fff', fontWeight: 600, cursor: loading ? 'wait' : 'pointer', opacity: loading ? 0.7 : 1 }}>
          {loading ? '학습 중…' : '백테스트 실행'}
        </button>
      </div>
      {err && <div style={{ color: 'var(--color-down)', fontSize: 12 }}>⚠ {err}</div>}
      {loading && (
        <div style={{ fontSize: 12, color: 'var(--color-muted)' }}>
          RL 학습은 알고리즘·에피소드 수에 따라 수 분이 소요됩니다…
        </div>
      )}
      {result && <MetricsPanel result={result} stockName={stockName} />}
    </div>
  );
}

// ─── 메인 페이지 ─────────────────────────────────────────────────────────────
export default function BacktestPage() {
  const router = useRouter();
  const [ticker,    setTicker]    = useState('005930');
  const [stockName, setStockName] = useState('');
  const [tab,       setTab]       = useState<'rule' | 'rl'>('rule');

  useEffect(() => {
    const saved     = localStorage.getItem('st_ticker') ?? '005930';
    const savedName = localStorage.getItem('st_name') ?? '';
    const local     = searchStocks(saved, 1).find(s => s.ticker === saved);
    const name      = local?.name ?? savedName;
    setTicker(saved);
    setStockName(name);
    if (!name && /^\d{6}$/.test(saved)) {
      fetch(`${BFF}/api/stocks/${saved}`, { signal: AbortSignal.timeout(2000) })
        .then(r => r.ok ? r.json() : null)
        .then(d => { if (d?.name) setStockName(d.name as string); })
        .catch(() => {});
    }
  }, []);

  function handleTickerChange(val: string) {
    const t = val.trim().toUpperCase();
    setTicker(t);
    setStockName('');
    // localStorage 동기화 — TopBar 반영
    if (/^\d{6}$/.test(t)) {
      try { localStorage.setItem('st_ticker', t); } catch { /* ignore */ }
    }
  }

  const tabBtn = (key: 'rule' | 'rl', label: string) => (
    <button onClick={() => setTab(key)} style={{
      padding: '8px 20px', border: 'none', fontWeight: 600, cursor: 'pointer', fontSize: 14,
      backgroundColor: 'transparent',
      color: tab === key ? 'var(--color-accent)' : 'var(--color-muted)',
      borderBottom: tab === key ? '2px solid var(--color-accent)' : '2px solid transparent',
    }}>{label}</button>
  );

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* 헤더 */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <h2 style={{ margin: 0, fontSize: 20, fontWeight: 700 }}>↺ 백테스팅</h2>
        <span style={{ padding: '2px 8px', borderRadius: 4, fontSize: 11, fontWeight: 600, backgroundColor: 'rgba(88,166,255,0.12)', color: 'var(--color-accent)' }}>
          Phase C F5
        </span>
        <button
          onClick={() => router.push('/strategy')}
          style={{ marginLeft: 'auto', padding: '4px 12px', borderRadius: 4, border: '1px solid var(--color-border)', backgroundColor: 'transparent', color: 'var(--color-muted)', fontSize: 12, cursor: 'pointer' }}
          title="스크리너로 이동"
        >
          ◎ 스크리너 →
        </button>
      </div>

      {/* 종목 선택 (공유) */}
      <div style={{ display: 'flex', gap: 12, padding: '12px 16px', backgroundColor: 'var(--color-card)', borderRadius: 8, border: '1px solid var(--color-border)', alignItems: 'flex-end', flexWrap: 'wrap' }}>
        <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 12 }}>
          종목코드
          <input
            value={ticker}
            onChange={e => handleTickerChange(e.target.value)}
            placeholder="005930"
            style={{ width: 110, padding: '4px 8px', borderRadius: 4, border: '1px solid var(--color-border)', backgroundColor: 'var(--color-bg)', color: 'var(--color-text)', fontFamily: 'monospace', textTransform: 'uppercase' }}
          />
        </label>
        {stockName && (
          <span style={{ fontSize: 14, fontWeight: 600, color: 'var(--color-text)', paddingBottom: 4 }}>{stockName}</span>
        )}
        <span style={{ fontSize: 11, color: 'var(--color-muted)', paddingBottom: 4 }}>
          대시보드 조회 종목을 자동 사용합니다.
        </span>
      </div>

      {/* 전략 탭 바 */}
      <div style={{ display: 'flex', borderBottom: '1px solid var(--color-border)' }}>
        {tabBtn('rule', '규칙기반 전략')}
        {tabBtn('rl',   '강화학습 전략')}
      </div>

      {/* 탭 콘텐츠 */}
      <div style={{ padding: 20, backgroundColor: 'var(--color-card)', borderRadius: 8, border: '1px solid var(--color-border)' }}>
        {tab === 'rule' && <RuleBasedTab ticker={ticker} stockName={stockName} />}
        {tab === 'rl'   && <RLTab        ticker={ticker} stockName={stockName} />}
      </div>
    </div>
  );
}
