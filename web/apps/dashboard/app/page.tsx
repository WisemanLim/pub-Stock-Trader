import { cookies } from 'next/headers';
import { getSnapshot } from '@/lib/api';
import { formatPrice, formatPct, signalColor } from '@/lib/format';
import CandleChart4 from '@/components/CandleChart4';
import SimulationPanel from '@/components/SimulationPanel';
import { Tooltip } from '@/components/Tooltip';
import { TOOLTIPS } from '@/lib/tooltips';
import { searchStocks } from '@/lib/stocks';

export default async function DashboardPage() {
  const cookieStore = await cookies();
  const rawTicker = cookieStore.get('st_ticker')?.value ?? '005930';
  // 한글·특수문자 등 무효 ticker 방어 — cookie 오염 시 기본값(005930)으로 폴백
  // KRX 6자리 숫자 또는 해외 1~5자 알파벳만 허용 — 그 외(7자리 숫자 등) 폴백
  const ticker = /^([0-9]{6}|[A-Za-z]{1,5})$/.test(rawTicker) ? rawTicker : '005930';
  const persona = cookieStore.get('st_persona')?.value ?? 'swing';

  let snapshot: Awaited<ReturnType<typeof getSnapshot>> | null = null;
  let connErr = false;
  try {
    snapshot = await getSnapshot(ticker, persona);
  } catch {
    connErr = true;
  }

  const ind = snapshot?.indicators;
  const dec = snapshot?.decision?.decision;
  const price = snapshot?.price?.price;

  const BFF = process.env.BFF_URL ?? 'http://localhost:3002';

  // 종목 메타: 로컬 static 목록 우선, 없으면 BFF 동적 조회
  const localEntry = searchStocks(ticker, 1).find((s) => s.ticker === ticker);
  let stockName: string | null = localEntry?.name ?? null;
  let stockMarket: string = localEntry?.market ?? 'KRX';
  if (!localEntry) {
    try {
      const metaRes = await fetch(`${BFF}/api/stocks/${ticker}`, {
        cache: 'no-store',
        signal: AbortSignal.timeout(2000),
      });
      if (metaRes.ok) {
        const meta = await metaRes.json();
        if (meta.found) {
          stockName = meta.name as string;
          stockMarket = (meta.market as string) ?? 'KRX';
        }
      }
    } catch { /* BFF 미기동 시 무시 */ }
  }

  // Phase B-6: 시장경보 + 공매도 병렬 조회
  type AlertRow = { ticker: string; name: string; level: string; date: string };
  type MarketAlertData = { alerts: AlertRow[]; count: number; caution: number; warning: number; danger: number };
  type ShortRow = { date: string; short_vol: number; short_val: number; short_ratio: number };
  type ShortSellData = { ticker: string; rows: ShortRow[]; count: number };

  let marketAlerts: MarketAlertData = { alerts: [], count: 0, caution: 0, warning: 0, danger: 0 };
  let shortSell: ShortSellData = { ticker, rows: [], count: 0 };

  try {
    const [alertRes, ssRes] = await Promise.allSettled([
      fetch(`${BFF}/api/market-alerts`, { cache: 'no-store', signal: AbortSignal.timeout(2000) }),
      fetch(`${BFF}/api/short-selling/${ticker}`, { cache: 'no-store', signal: AbortSignal.timeout(2000) }),
    ]);
    if (alertRes.status === 'fulfilled' && alertRes.value.ok) {
      const raw = await alertRes.value.json() as { alerts?: AlertRow[]; count?: number; by_level?: Record<string, number> };
      const byLevel = raw.by_level ?? {};
      marketAlerts = {
        alerts: raw.alerts ?? [],
        count: raw.count ?? 0,
        caution: byLevel['투자주의'] ?? 0,
        warning: byLevel['투자경고'] ?? 0,
        danger: (byLevel['투자위험'] ?? 0) + (byLevel['위험예고'] ?? 0),
      };
    }
    if (ssRes.status === 'fulfilled' && ssRes.value.ok) {
      const raw = await ssRes.value.json();
      shortSell = { ticker: raw.ticker ?? ticker, rows: raw.rows ?? [], count: raw.count ?? 0 };
    }
  } catch { /* 서비스 미기동 시 무시 */ }

  // D-5: ESG 점수
  type EsgData = { ticker: string; esg_score: number | null; e_score: number | null; s_score: number | null; g_score: number | null };
  let esg: EsgData | null = null;
  try {
    const esgRes = await fetch(`${BFF}/api/esg/${ticker}`, { cache: 'no-store', signal: AbortSignal.timeout(2000) });
    if (esgRes.ok) esg = await esgRes.json() as EsgData;
  } catch { /* ESG 서비스 미기동 무시 */ }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* Connection error banner */}
      {connErr && (
        <div
          style={{
            padding: '10px 16px',
            backgroundColor: 'rgba(248,81,73,0.12)',
            border: '1px solid rgba(248,81,73,0.4)',
            borderRadius: 6,
            color: 'var(--color-down)',
            fontSize: 13,
          }}
        >
          ⚠ BFF(:3002) 연결 실패 — 서비스 기동 후 새로고침하세요.
          <span style={{ color: 'var(--color-muted)', marginLeft: 8, fontSize: 11 }}>
            로컬: <code>make local-all</code> &nbsp;|&nbsp; 프로덕션: <code>make prod-all</code>
          </span>
        </div>
      )}

      {/* Ticker header */}
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 16 }}>
        <h1
          className="mono"
          style={{ margin: 0, fontSize: 22, fontWeight: 700, color: 'var(--color-text)' }}
        >
          {ticker}
        </h1>
        {stockName != null && (
          <span
            style={{ fontSize: 20, fontWeight: 600, color: 'var(--color-text)' }}
          >
            {stockName}
          </span>
        )}
        <Tooltip title={stockMarket} content={TOOLTIPS.misc.kospi}>
          <span
            style={{
              padding: '2px 8px',
              borderRadius: 4,
              fontSize: 11,
              fontWeight: 600,
              letterSpacing: 0.8,
              backgroundColor: stockMarket === 'KOSDAQ'
                ? 'rgba(63,185,80,0.12)' : 'rgba(88,166,255,0.12)',
              color: stockMarket === 'KOSDAQ'
                ? 'var(--color-up)' : 'var(--color-accent)',
              border: stockMarket === 'KOSDAQ'
                ? '1px solid rgba(63,185,80,0.25)' : '1px solid rgba(88,166,255,0.25)',
              cursor: 'help',
            }}
          >
            {stockMarket}
          </span>
        </Tooltip>
        <Tooltip title="페르소나" content={TOOLTIPS.misc.persona}>
          <span
            style={{
              padding: '2px 8px',
              borderRadius: 4,
              fontSize: 11,
              color: 'var(--color-muted)',
              border: '1px solid var(--color-border)',
              cursor: 'help',
            }}
          >
            {persona}
          </span>
        </Tooltip>
      </div>

      {/* Metric cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 12 }}>
        <MetricCard title="현재가" mono tooltip={TOOLTIPS.indicator.currentPrice}>
          {price != null ? formatPrice(price) : '—'}
        </MetricCard>
        <MetricCard title="RSI (14)" mono tooltip={TOOLTIPS.indicator.rsi}>
          <span style={{ color: rsiColor(ind?.rsi) }}>{ind?.rsi ?? '—'}</span>
        </MetricCard>
        <MetricCard title="Bollinger" tooltip={TOOLTIPS.indicator.bollinger}>
          <span style={{ fontSize: 12, color: 'var(--color-muted)' }}>
            {ind?.bollinger != null
              ? `↑${formatPrice(ind.bollinger.upper)} ↓${formatPrice(ind.bollinger.lower)}`
              : '—'}
          </span>
        </MetricCard>
        <MetricCard title="지표 시그널" tooltip={TOOLTIPS.indicator.signal}>
          <SignalBadge signal={ind?.signal} />
        </MetricCard>
        <MetricCard title="에이전트 결정" tooltip={TOOLTIPS.indicator.agentDecision}>
          <SignalBadge signal={dec?.signal} />
          {dec && (
            <div style={{ fontSize: 11, color: 'var(--color-muted)', marginTop: 4 }}>
              비중 {formatPct((dec.weight ?? 0) * 100)} · 신뢰도 {formatPct((dec.confidence ?? 0) * 100)}
            </div>
          )}
        </MetricCard>
      </div>

      {/* Main grid: [chart + bottom panels] | side panels */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 264px', gap: 16, alignItems: 'start' }}>
        {/* Left column: chart + bottom panels */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {/* Candle chart */}
          <Panel title="캔들 차트" badge="F6.2" tooltip={TOOLTIPS.panel.candleChart}>
            <CandleChart4 ticker={ticker} />
          </Panel>

          {/* Bottom row: market alerts + short selling + position */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 12 }}>
        <Panel title="시장경보" badge="Phase B" tooltip={TOOLTIPS.panel.marketAlert}>
          {marketAlerts.count === 0 ? (
            <div style={{ color: 'var(--color-up)', fontSize: 12 }}>✓ 이상 종목 없음</div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              {marketAlerts.alerts.slice(0, 4).map((a, i) => (
                <div key={i} style={{ display: 'flex', gap: 6, alignItems: 'center', fontSize: 11 }}>
                  <span style={{
                    padding: '1px 5px', borderRadius: 3, fontSize: 10, fontWeight: 600,
                    backgroundColor: a.level.includes('위험') ? 'rgba(248,81,73,0.18)' : a.level.includes('경고') ? 'rgba(230,162,0,0.18)' : 'rgba(88,166,255,0.18)',
                    color: a.level.includes('위험') ? 'var(--color-down)' : a.level.includes('경고') ? '#f0a500' : 'var(--color-accent)',
                  }}>{a.level}</span>
                  <span className="mono" style={{ color: 'var(--color-text)' }}>{a.ticker}</span>
                  <span style={{ color: 'var(--color-muted)' }}>{a.name}</span>
                </div>
              ))}
            </div>
          )}
          <div style={{ fontSize: 11, color: 'var(--color-muted)', marginTop: 6 }}>
            투자주의 {marketAlerts.caution} · 경고 {marketAlerts.warning} · 위험 {marketAlerts.danger}
          </div>
        </Panel>
        <Panel title="공매도" badge="Phase B" tooltip={TOOLTIPS.panel.shortSelling}>
          {shortSell.rows.length === 0 ? (
            <div style={{ fontSize: 12, color: 'var(--color-muted)' }}>데이터 없음 (KRX API 연동)</div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
              {shortSell.rows.slice(0, 4).map((r, i) => (
                <div key={i} style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11 }}>
                  <span style={{ color: 'var(--color-muted)' }}>{r.date}</span>
                  <span className="mono" style={{
                    color: r.short_ratio > 0.2 ? 'var(--color-down)' : r.short_ratio > 0.1 ? '#f0a500' : 'var(--color-text)',
                  }}>{(r.short_ratio * 100).toFixed(2)}%</span>
                </div>
              ))}
            </div>
          )}
          {shortSell.rows[0] && (
            <div style={{ fontSize: 11, color: 'var(--color-muted)', marginTop: 6 }}>
              최근 비율 {(shortSell.rows[0].short_ratio * 100).toFixed(2)}% · {shortSell.count}일 데이터
            </div>
          )}
        </Panel>
        <Panel title="매수/매도" badge="SIMULATION" tooltip={TOOLTIPS.panel.position}>
          <SimulationPanel ticker={ticker} price={price ?? undefined} />
        </Panel>
          </div>{/* /bottom row */}
        </div>{/* /left column */}

        {/* Right side panels */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {/* Technical indicators */}
          <Panel title="기술지표" tooltip={TOOLTIPS.panel.indicators}>
            <IndRow label="RSI" value={ind?.rsi} color={rsiColor(ind?.rsi)} tooltip={TOOLTIPS.indicator.rsi} />
            <IndRow label="MACD" value={ind?.macd?.macd} tooltip={TOOLTIPS.indicator.macd} />
            <IndRow label="Signal" value={ind?.macd?.signal} tooltip={TOOLTIPS.indicator.macdSignal} />
            <IndRow label="Hist" value={ind?.macd?.histogram} tooltip={TOOLTIPS.indicator.macd} />
            <IndRow label="ATR" value={ind?.atr} tooltip={TOOLTIPS.indicator.atr} />
            <IndRow label="EMA(20)" value={ind?.ema_20 != null ? formatPrice(ind.ema_20) : null} tooltip={TOOLTIPS.indicator.ema20} />
            <IndRow label="SMA(50)" value={ind?.sma_50 != null ? formatPrice(ind.sma_50) : null} tooltip={TOOLTIPS.indicator.sma20} />
            <IndRow label="VWAP(20)" value={ind?.vwap_20 != null ? formatPrice(ind.vwap_20) : null} tooltip="거래량 가중 평균 가격 (20일)" />
            <IndRow label="Close%" value={ind?.close_pct != null ? `${(ind.close_pct * 100).toFixed(1)}%` : null} tooltip="당일 가격 위치 (저가=0%, 고가=100%)" />
          </Panel>

          {/* Investor flow — KRX Phase A data */}
          <Panel title="수급 동향" badge="Phase A" tooltip={TOOLTIPS.panel.flow}>
            <FlowPlaceholder />
          </Panel>

          {/* Risk status */}
          <Panel title="리스크 상태" tooltip={TOOLTIPS.panel.riskStatus}>
            <RiskRow label="Stop-Loss" value="-2.0%" status="active" tooltip={TOOLTIPS.risk.stopLoss} />
            <RiskRow label="일일한도" value="-5.0%" status="active" tooltip={TOOLTIPS.risk.dailyLimit} />
            <RiskRow label="포지션 한도" value="10%" status="active" tooltip={TOOLTIPS.risk.positionLimit} />
          </Panel>

          {/* D-5: ESG 점수 위젯 */}
          <Panel title="ESG 점수" badge="Phase D">
            {esg == null || esg.esg_score == null ? (
              <div style={{ fontSize: 12, color: 'var(--color-muted)' }}>ingest(:8003) 연동 후 표시</div>
            ) : (
              <>
                <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, marginBottom: 10 }}>
                  <span style={{
                    fontSize: 28, fontWeight: 800,
                    color: esg.esg_score >= 70 ? 'var(--color-up)' : esg.esg_score >= 50 ? '#f0a500' : 'var(--color-down)',
                  }}>{esg.esg_score.toFixed(1)}</span>
                  <span style={{ fontSize: 11, color: 'var(--color-muted)' }}>/100</span>
                </div>
                {[
                  { label: 'E (환경)', value: esg.e_score, max: 20 },
                  { label: 'S (사회)', value: esg.s_score, max: 30 },
                  { label: 'G (지배구조)', value: esg.g_score, max: 50 },
                ].map(({ label, value, max }) => (
                  <div key={label} style={{ marginBottom: 6 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, marginBottom: 3 }}>
                      <span style={{ color: 'var(--color-muted)' }}>{label}</span>
                      <span style={{ fontFamily: 'monospace' }}>{value != null ? value.toFixed(1) : '-'}/{max}</span>
                    </div>
                    <div style={{ height: 4, backgroundColor: 'var(--color-border)', borderRadius: 2 }}>
                      <div style={{
                        height: 4, borderRadius: 2,
                        width: value != null ? `${Math.min((value / max) * 100, 100)}%` : '0%',
                        backgroundColor: value != null && value / max >= 0.7 ? 'var(--color-up)' : value != null && value / max >= 0.5 ? '#f0a500' : 'var(--color-down)',
                      }} />
                    </div>
                  </div>
                ))}
              </>
            )}
          </Panel>
        </div>{/* /right panels */}
      </div>{/* /main grid */}
    </div>
  );
}

/* ── Sub-components ───────────────────────────────────────────── */

function Panel({
  title,
  badge,
  tooltip,
  children,
}: {
  title: string;
  badge?: string;
  tooltip?: string;
  children: React.ReactNode;
}) {
  return (
    <div
      style={{
        backgroundColor: 'var(--color-card)',
        border: '1px solid var(--color-border)',
        borderRadius: 8,
        padding: 16,
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
        {tooltip ? (
          <Tooltip title={title} content={tooltip}>
            <span
              style={{
                fontSize: 12, fontWeight: 600, color: 'var(--color-muted)',
                borderBottom: '1px dotted var(--color-border)', cursor: 'help',
              }}
            >
              {title.toUpperCase()}
            </span>
          </Tooltip>
        ) : (
          <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--color-muted)' }}>
            {title.toUpperCase()}
          </span>
        )}
        {badge && (
          <span
            style={{
              fontSize: 9, padding: '1px 5px', borderRadius: 3,
              backgroundColor: 'rgba(88,166,255,0.1)', color: 'var(--color-accent)',
              border: '1px solid rgba(88,166,255,0.2)', fontWeight: 700, letterSpacing: 0.5,
            }}
          >
            {badge}
          </span>
        )}
      </div>
      {children}
    </div>
  );
}

function MetricCard({
  title,
  mono,
  tooltip,
  children,
}: {
  title: string;
  mono?: boolean;
  tooltip?: string;
  children: React.ReactNode;
}) {
  return (
    <div
      style={{
        backgroundColor: 'var(--color-card)',
        border: '1px solid var(--color-border)',
        borderRadius: 8,
        padding: '12px 16px',
      }}
    >
      <div style={{ fontSize: 10, color: 'var(--color-muted)', letterSpacing: 0.8, marginBottom: 6 }}>
        {tooltip ? (
          <Tooltip title={title} content={tooltip}>
            <span style={{ borderBottom: '1px dotted var(--color-border)', cursor: 'help' }}>
              {title.toUpperCase()}
            </span>
          </Tooltip>
        ) : title.toUpperCase()}
      </div>
      <div
        className={mono ? 'mono' : ''}
        style={{ fontSize: 20, fontWeight: 700, color: 'var(--color-text)', lineHeight: 1.2 }}
      >
        {children}
      </div>
    </div>
  );
}

function SignalBadge({ signal }: { signal?: string }) {
  if (!signal) return <span style={{ color: 'var(--color-muted)' }}>—</span>;
  const color =
    signal === 'BUY' ? 'var(--color-up)'
    : signal === 'SELL' ? 'var(--color-down)'
    : 'var(--color-warn)';
  const bg =
    signal === 'BUY' ? 'rgba(63,185,80,0.12)'
    : signal === 'SELL' ? 'rgba(248,81,73,0.12)'
    : 'rgba(210,153,34,0.12)';
  return (
    <span
      style={{
        padding: '3px 10px',
        borderRadius: 4,
        backgroundColor: bg,
        color,
        fontWeight: 700,
        fontSize: 16,
        border: `1px solid ${color}40`,
      }}
    >
      {signal}
    </span>
  );
}

function IndRow({ label, value, color, tooltip }: { label: string; value?: number | string | null; color?: string; tooltip?: string }) {
  return (
    <div
      style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        padding: '4px 0',
        borderBottom: '1px solid var(--color-border)',
      }}
    >
      <span style={{ fontSize: 11, color: 'var(--color-muted)' }}>
        {tooltip ? (
          <Tooltip content={tooltip} title={label}>
            <span style={{ borderBottom: '1px dotted var(--color-border)', cursor: 'help' }}>{label}</span>
          </Tooltip>
        ) : label}
      </span>
      <span
        className="mono"
        style={{ fontSize: 12, fontWeight: 600, color: color ?? 'var(--color-text)' }}
      >
        {value != null ? String(value) : '—'}
      </span>
    </div>
  );
}

function RiskRow({ label, value, status, tooltip }: { label: string; value: string; status: string; tooltip?: string }) {
  return (
    <div
      style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        padding: '4px 0',
        borderBottom: '1px solid var(--color-border)',
      }}
    >
      <span style={{ fontSize: 11, color: 'var(--color-muted)' }}>
        {tooltip ? (
          <Tooltip content={tooltip} title={label}>
            <span style={{ borderBottom: '1px dotted var(--color-border)', cursor: 'help' }}>{label}</span>
          </Tooltip>
        ) : label}
      </span>
      <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
        <span className="mono" style={{ fontSize: 12, color: 'var(--color-down)' }}>
          {value}
        </span>
        <span
          style={{
            width: 6,
            height: 6,
            borderRadius: '50%',
            backgroundColor: status === 'active' ? 'var(--color-up)' : 'var(--color-muted)',
          }}
        />
      </div>
    </div>
  );
}

function FlowPlaceholder() {
  const rows = [
    { label: '기관',   value: '+125억', color: 'var(--color-up)',   tooltip: TOOLTIPS.flow.institution },
    { label: '외국인', value: '-48억',  color: 'var(--color-down)', tooltip: TOOLTIPS.flow.foreign     },
    { label: '개인',   value: '-77억',  color: 'var(--color-down)', tooltip: TOOLTIPS.flow.individual  },
  ];
  return (
    <div>
      {rows.map((r) => (
        <div
          key={r.label}
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            padding: '4px 0',
            borderBottom: '1px solid var(--color-border)',
          }}
        >
          <span style={{ fontSize: 11, color: 'var(--color-muted)' }}>
            <Tooltip title={r.label} content={r.tooltip}>
              <span style={{ borderBottom: '1px dotted var(--color-border)', cursor: 'help' }}>{r.label}</span>
            </Tooltip>
          </span>
          <span className="mono" style={{ fontSize: 12, fontWeight: 600, color: r.color }}>
            {r.value}
          </span>
        </div>
      ))}
      <div style={{ fontSize: 10, color: 'var(--color-muted)', marginTop: 6 }}>
        * KRX 투자자별 거래실적 (Phase A 연동 예정)
      </div>
    </div>
  );
}

function rsiColor(rsi?: number | null): string {
  if (rsi == null) return 'var(--color-text)';
  if (rsi >= 70) return 'var(--color-down)';
  if (rsi <= 30) return 'var(--color-up)';
  return 'var(--color-text)';
}
