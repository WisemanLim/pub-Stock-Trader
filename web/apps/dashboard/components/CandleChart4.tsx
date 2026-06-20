'use client';

import { useEffect, useRef, useState } from 'react';
import type { CSSProperties } from 'react';
import CandleChart from './CandleChart';
import type { Candle, CandleResponse } from '@/lib/candles';

const BFF = process.env.NEXT_PUBLIC_BFF_URL ?? 'http://localhost:3002';
// QUAD_H × 2 = 660px (original single chart height)
const QUAD_H = 330;
const YAXIS_W = 58;
const XAXIS_H = 22;
const TITLE_H = 26;
const MODAL_CHART_H = 540;

interface IntradayBar {
  datetime: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

type QuadKey = 'q1' | 'q2' | 'q3' | 'q4';

// ── 공통 SVG 유틸 ──────────────────────────────────────────────
function sy(v: number, min: number, max: number, h: number): number {
  if (max === min) return h / 2;
  return h - ((v - min) / (max - min)) * h;
}

function niceYTicks(min: number, max: number, n = 4): number[] {
  if (max === min) return [Math.round(min)];
  const range = max - min;
  const rough = range / n;
  const pow = Math.pow(10, Math.floor(Math.log10(rough)));
  const interval = ([1, 2, 2.5, 5, 10].find(f => f * pow >= rough) ?? 10) * pow;
  const start = Math.ceil(min / interval) * interval;
  const ticks: number[] = [];
  for (let t = start; t <= max + interval * 0.01; t += interval) {
    const v = Math.round(t * 100) / 100;
    if (v >= min && v <= max) ticks.push(v);
  }
  return ticks;
}

// ── 확대 버튼 ──────────────────────────────────────────────────
function ExpandBtn({ onClick }: { onClick: () => void }) {
  return (
    <button
      onClick={e => { e.stopPropagation(); onClick(); }}
      title="전체화면"
      style={{
        position: 'absolute', top: 5, right: 6, zIndex: 3,
        background: 'none', border: '1px solid var(--color-border)',
        borderRadius: 3, padding: '1px 5px', cursor: 'pointer',
        fontSize: 11, color: 'var(--color-muted)', lineHeight: 1.3,
      }}
    >⛶</button>
  );
}

// ── Q1: 금일(또는 최근 거래일) 5분봉 선형 차트 ───────────────────
function IntradayLineChart({ ticker, height = QUAD_H, onExpand }: { ticker: string; height?: number; onExpand?: () => void }) {
  const [bars, setBars] = useState<IntradayBar[]>([]);
  const [err, setErr] = useState('');
  const [w, setW] = useState(400);
  const [visCount, setVisCount] = useState(78);
  const [tooltip, setTooltip] = useState<{ x: number; y: number; price: number; time: string } | null>(null);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = ref.current; if (!el) return;
    const ro = new ResizeObserver(e => setW(Math.floor(e[0].contentRect.width)));
    ro.observe(el); return () => ro.disconnect();
  }, []);

  useEffect(() => {
    if (!ticker) return;
    fetch(`${BFF}/api/intraday/${ticker}?interval=5m`, { cache: 'no-store' })
      .then(r => r.ok ? r.json() : Promise.reject(r.status))
      .then(d => setBars(Array.isArray(d?.bars) ? d.bars : []))
      .catch(e => setErr(String(e)));
  }, [ticker]);

  const today = new Date().toISOString().slice(0, 10);
  // 오늘 데이터 없으면 최근 거래일 데이터 표시
  const todayBars = bars.filter(b => b.datetime.startsWith(today));
  const lastDay = bars.length > 0 ? bars[bars.length - 1].datetime.slice(0, 10) : '';
  const sessionBars = todayBars.length > 0 ? todayBars : (lastDay ? bars.filter(b => b.datetime.startsWith(lastDay)) : bars);
  const totalBars = sessionBars.length > 0 ? sessionBars : bars;
  const display = totalBars.slice(-Math.min(visCount, totalBars.length));

  const innerH = height - XAXIS_H - TITLE_H;
  const chartW = w - YAXIS_W;

  const closes = display.map(b => b.close).filter(v => v > 0);
  const minV = closes.length > 0 ? Math.min(...closes) * 0.9995 : 0;
  const maxV = closes.length > 0 ? Math.max(...closes) * 1.0005 : 1;
  const yTicks = niceYTicks(minV, maxV);

  const pts = display.map((b, i) => {
    const x = (i / Math.max(display.length - 1, 1)) * chartW;
    const y = sy(b.close, minV, maxV, innerH);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(' ');

  const xLabels: { x: number; label: string }[] = [];
  if (display.length > 1) {
    const step = Math.max(1, Math.floor(display.length / 6));
    for (let i = 0; i < display.length; i += step) {
      xLabels.push({
        x: (i / Math.max(display.length - 1, 1)) * chartW,
        label: display[i].datetime.split(' ')[1]?.slice(0, 5) ?? '',
      });
    }
  }

  const isToday = lastDay === today || todayBars.length > 0;
  const dateLabel = display.length > 0 ? display[0].datetime.slice(0, 10) : '';

  function handleWheel(e: React.WheelEvent<SVGSVGElement>) {
    e.preventDefault();
    setVisCount(prev => Math.max(10, Math.min(totalBars.length || 200, prev + (e.deltaY > 0 ? 10 : -10))));
  }

  function handleMouseMove(e: React.MouseEvent<SVGSVGElement>) {
    const rect = e.currentTarget.getBoundingClientRect();
    const svgX = (e.clientX - rect.left) * (w / rect.width);
    if (svgX >= chartW || display.length < 2) { setTooltip(null); return; }
    const idx = Math.round((svgX / chartW) * (display.length - 1));
    const b = display[Math.max(0, Math.min(display.length - 1, idx))];
    if (b) setTooltip({ x: e.clientX, y: e.clientY, price: b.close, time: b.datetime.split(' ')[1]?.slice(0, 5) ?? '' });
  }

  return (
    <div ref={ref} style={{ width: '100%', position: 'relative' }}>
      <div style={{ fontSize: 11, color: 'var(--color-muted)', padding: '4px 8px 0', fontWeight: 600, height: TITLE_H, display: 'flex', alignItems: 'center', gap: 6 }}>
        금일 5분봉
        {dateLabel && <span style={{ fontWeight: 400, fontSize: 10 }}>({dateLabel}{!isToday ? ' · 장마감' : ''})</span>}
        <span style={{ fontSize: 9, opacity: 0.5 }}>스크롤 줌 · {display.length}봉</span>
      </div>
      {onExpand && <ExpandBtn onClick={onExpand} />}
      {err && <div style={{ fontSize: 10, color: 'var(--color-down)', padding: '2px 8px' }}>⚠ {err}</div>}
      {display.length === 0 ? (
        <div style={{ height: height - TITLE_H, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--color-muted)', fontSize: 12 }}>데이터 없음</div>
      ) : (
        <svg width={w} height={height - TITLE_H} style={{ display: 'block', cursor: 'crosshair', userSelect: 'none' }}
          onWheel={handleWheel} onMouseMove={handleMouseMove} onMouseLeave={() => setTooltip(null)}>
          {/* Y gridlines + labels */}
          {yTicks.map(tick => {
            const y = sy(tick, minV, maxV, innerH);
            return (
              <g key={tick}>
                <line x1={0} x2={chartW} y1={y} y2={y} stroke="var(--color-border)" strokeWidth={1} strokeDasharray="3,4" />
                <text x={chartW + 3} y={y + 4} fontSize={9} fill="var(--color-muted)">{tick >= 1000 ? tick.toLocaleString('ko-KR') : tick}</text>
              </g>
            );
          })}
          {/* Axes */}
          <line x1={chartW} x2={chartW} y1={0} y2={innerH} stroke="var(--color-border)" strokeWidth={1} />
          <line x1={0} x2={chartW} y1={innerH} y2={innerH} stroke="var(--color-border)" strokeWidth={1} />
          {/* Price line */}
          {display.length > 1 && <polyline points={pts} fill="none" stroke="var(--color-accent)" strokeWidth={1.5} />}
          {/* Last dot */}
          {display.length > 0 && (() => {
            const y = sy(display[display.length - 1].close, minV, maxV, innerH);
            return <circle cx={chartW} cy={y} r={3} fill="var(--color-accent)" />;
          })()}
          {/* X labels */}
          {xLabels.map(({ x, label }, i) => (
            <text key={i} x={x} y={innerH + XAXIS_H - 4} fontSize={9} fill="var(--color-muted)" textAnchor="middle">{label}</text>
          ))}
        </svg>
      )}
      {tooltip && (
        <div style={{ position: 'fixed', left: tooltip.x + 12, top: tooltip.y - 10, backgroundColor: 'var(--color-card)', border: '1px solid var(--color-border)', borderRadius: 4, padding: '4px 8px', fontSize: 11, pointerEvents: 'none', zIndex: 9999 }}>
          <span style={{ color: 'var(--color-muted)', marginRight: 4 }}>{tooltip.time}</span>
          <span style={{ fontWeight: 700 }}>{tooltip.price.toLocaleString('ko-KR')}원</span>
        </div>
      )}
    </div>
  );
}

// ── Q2: 시간대별 평균 수익률 ────────────────────────────────────
function HourlyPatternChart({ ticker, height = QUAD_H, onExpand }: { ticker: string; height?: number; onExpand?: () => void }) {
  const [bars, setBars] = useState<IntradayBar[]>([]);
  const [err, setErr] = useState('');
  const [w, setW] = useState(400);
  const [yZoom, setYZoom] = useState(1);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = ref.current; if (!el) return;
    const ro = new ResizeObserver(e => setW(Math.floor(e[0].contentRect.width)));
    ro.observe(el); return () => ro.disconnect();
  }, []);

  useEffect(() => {
    if (!ticker) return;
    fetch(`${BFF}/api/intraday/${ticker}?interval=5m`, { cache: 'no-store' })
      .then(r => r.ok ? r.json() : Promise.reject(r.status))
      .then(d => setBars(Array.isArray(d?.bars) ? d.bars : []))
      .catch(e => setErr(String(e)));
  }, [ticker]);

  // 날짜별 그룹 → 시간대별 수익률(일 개장 대비 누적)
  const hourReturns: Record<number, number[]> = {};
  const dayGroups: Record<string, IntradayBar[]> = {};
  for (const b of bars) (dayGroups[b.datetime.slice(0, 10)] ??= []).push(b);
  for (const dBars of Object.values(dayGroups)) {
    const sorted = [...dBars].sort((a, b) => a.datetime.localeCompare(b.datetime));
    const dayOpen = sorted[0]?.open ?? 0;
    if (dayOpen === 0) continue;
    const hGroups: Record<number, IntradayBar[]> = {};
    for (const b of sorted) {
      const h = parseInt(b.datetime.split(' ')[1]?.split(':')[0] ?? '0');
      if (h >= 9 && h <= 15) (hGroups[h] ??= []).push(b);
    }
    for (const [hStr, hBars] of Object.entries(hGroups)) {
      const h = parseInt(hStr);
      const last = hBars[hBars.length - 1].close;
      (hourReturns[h] ??= []).push((last - dayOpen) / dayOpen * 100);
    }
  }

  const HOURS = [9, 10, 11, 12, 13, 14, 15];
  const avgs = HOURS.map(h => {
    const vals = hourReturns[h];
    return vals?.length ? vals.reduce((a, b) => a + b, 0) / vals.length : 0;
  });

  const innerH = height - XAXIS_H - TITLE_H;
  const chartW = w - YAXIS_W;
  const maxAbsRaw = Math.max(...avgs.map(Math.abs), 0.05);
  const maxAbs = maxAbsRaw / yZoom;
  const barW = Math.max(8, chartW / HOURS.length * 0.62);

  function yScale(v: number) { return innerH / 2 - (Math.max(-maxAbs, Math.min(maxAbs, v)) / maxAbs) * (innerH / 2 - 6); }

  function handleWheel(e: React.WheelEvent<SVGSVGElement>) {
    e.preventDefault();
    setYZoom(prev => Math.max(0.2, Math.min(8, prev + (e.deltaY > 0 ? -0.2 : 0.2))));
  }

  const noData = avgs.every(v => Math.abs(v) < 0.001);

  return (
    <div ref={ref} style={{ width: '100%', position: 'relative' }}>
      <div style={{ fontSize: 11, color: 'var(--color-muted)', padding: '4px 8px 0', fontWeight: 600, height: TITLE_H, display: 'flex', alignItems: 'center', gap: 6 }}>
        시간대별 평균 수익률
        <span style={{ fontSize: 9, opacity: 0.5 }}>스크롤 Y줌</span>
      </div>
      {onExpand && <ExpandBtn onClick={onExpand} />}
      {err && <div style={{ fontSize: 10, color: 'var(--color-down)', padding: '2px 8px' }}>⚠ {err}</div>}
      <svg width={w} height={height - TITLE_H} style={{ display: 'block', cursor: 'ns-resize', userSelect: 'none' }} onWheel={handleWheel}>
        {/* Grid lines */}
        {[0.25, 0.5, 0.75].map(f => {
          const y = f * innerH;
          return <line key={f} x1={0} x2={chartW} y1={y} y2={y} stroke="var(--color-border)" strokeWidth={1} strokeDasharray={f === 0.5 ? undefined : '3,4'} />;
        })}
        {/* Y axis + labels */}
        <line x1={chartW} x2={chartW} y1={0} y2={innerH} stroke="var(--color-border)" strokeWidth={1} />
        <text x={chartW + 3} y={8} fontSize={9} fill="var(--color-muted)">+{maxAbs.toFixed(2)}%</text>
        <text x={chartW + 3} y={innerH / 2 + 4} fontSize={9} fill="var(--color-muted)">0%</text>
        <text x={chartW + 3} y={innerH} fontSize={9} fill="var(--color-muted)">-{maxAbs.toFixed(2)}%</text>
        {/* X axis */}
        <line x1={0} x2={chartW} y1={innerH} y2={innerH} stroke="var(--color-border)" strokeWidth={1} />
        {/* Bars */}
        {HOURS.map((h, i) => {
          const x = (i + 0.5) / HOURS.length * chartW;
          const v = avgs[i];
          const y0 = innerH / 2;
          const y1 = yScale(v);
          const bTop = Math.min(y0, y1);
          const bH = Math.abs(y0 - y1);
          const color = v >= 0 ? 'var(--color-up)' : 'var(--color-down)';
          return (
            <g key={h}>
              <rect x={x - barW / 2} y={bTop} width={barW} height={Math.max(bH, 1)} fill={color} opacity={0.85} />
              <text x={x} y={innerH + XAXIS_H - 4} fontSize={9} fill="var(--color-muted)" textAnchor="middle">{h}시</text>
              {bH > 14 && (
                <text x={x} y={v >= 0 ? bTop - 2 : bTop + bH + 10} fontSize={8} fill={color} textAnchor="middle">
                  {v >= 0 ? '+' : ''}{v.toFixed(2)}%
                </text>
              )}
            </g>
          );
        })}
        {noData && (
          <text x={chartW / 2} y={innerH / 2 + 4} fontSize={11} fill="var(--color-muted)" textAnchor="middle">데이터 집계 중…</text>
        )}
      </svg>
    </div>
  );
}

// ── Q3: 요일별 평균 수익률 ─────────────────────────────────────
const KR_DAYS = ['일', '월', '화', '수', '목', '금', '토'];
const TRADING_DAYS = [1, 2, 3, 4, 5];

function WeekdayPatternChart({ ticker, height = QUAD_H, onExpand }: { ticker: string; height?: number; onExpand?: () => void }) {
  const [candles, setCandles] = useState<Candle[]>([]);
  const [err, setErr] = useState('');
  const [w, setW] = useState(400);
  const [yZoom, setYZoom] = useState(1);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = ref.current; if (!el) return;
    const ro = new ResizeObserver(e => setW(Math.floor(e[0].contentRect.width)));
    ro.observe(el); return () => ro.disconnect();
  }, []);

  useEffect(() => {
    if (!ticker) return;
    fetch(`${BFF}/api/candles/${ticker}?days=90`, { cache: 'no-store' })
      .then(r => r.ok ? r.json() : Promise.reject(r.status))
      .then((d: CandleResponse) => setCandles(d.bars ?? []))
      .catch(e => setErr(String(e)));
  }, [ticker]);

  const dowMap: Record<number, number[]> = {};
  for (const c of candles) {
    if (!c.date || c.open === 0) continue;
    const dow = new Date(c.date).getDay();
    (dowMap[dow] ??= []).push((c.close - c.open) / c.open * 100);
  }
  const avgs = TRADING_DAYS.map(d => {
    const vals = dowMap[d];
    return vals?.length ? vals.reduce((a, b) => a + b, 0) / vals.length : 0;
  });

  const innerH = height - XAXIS_H - TITLE_H;
  const chartW = w - YAXIS_W;
  const maxAbsRaw = Math.max(...avgs.map(Math.abs), 0.05);
  const maxAbs = maxAbsRaw / yZoom;
  const barW = Math.max(16, chartW / TRADING_DAYS.length * 0.55);

  function yScale(v: number) { return innerH / 2 - (Math.max(-maxAbs, Math.min(maxAbs, v)) / maxAbs) * (innerH / 2 - 6); }

  function handleWheel(e: React.WheelEvent<SVGSVGElement>) {
    e.preventDefault();
    setYZoom(prev => Math.max(0.2, Math.min(8, prev + (e.deltaY > 0 ? -0.2 : 0.2))));
  }

  return (
    <div ref={ref} style={{ width: '100%', position: 'relative' }}>
      <div style={{ fontSize: 11, color: 'var(--color-muted)', padding: '4px 8px 0', fontWeight: 600, height: TITLE_H, display: 'flex', alignItems: 'center', gap: 6 }}>
        요일별 평균 수익률 <span style={{ fontWeight: 400, fontSize: 10 }}>(90일)</span>
        <span style={{ fontSize: 9, opacity: 0.5 }}>스크롤 Y줌</span>
      </div>
      {onExpand && <ExpandBtn onClick={onExpand} />}
      {err && <div style={{ fontSize: 10, color: 'var(--color-down)', padding: '2px 8px' }}>⚠ {err}</div>}
      <svg width={w} height={height - TITLE_H} style={{ display: 'block', cursor: 'ns-resize', userSelect: 'none' }} onWheel={handleWheel}>
        {[0.25, 0.5, 0.75].map(f => {
          const y = f * innerH;
          return <line key={f} x1={0} x2={chartW} y1={y} y2={y} stroke="var(--color-border)" strokeWidth={1} strokeDasharray={f === 0.5 ? undefined : '3,4'} />;
        })}
        <line x1={chartW} x2={chartW} y1={0} y2={innerH} stroke="var(--color-border)" strokeWidth={1} />
        <text x={chartW + 3} y={8} fontSize={9} fill="var(--color-muted)">+{maxAbs.toFixed(2)}%</text>
        <text x={chartW + 3} y={innerH / 2 + 4} fontSize={9} fill="var(--color-muted)">0%</text>
        <text x={chartW + 3} y={innerH} fontSize={9} fill="var(--color-muted)">-{maxAbs.toFixed(2)}%</text>
        <line x1={0} x2={chartW} y1={innerH} y2={innerH} stroke="var(--color-border)" strokeWidth={1} />
        {TRADING_DAYS.map((d, i) => {
          const x = (i + 0.5) / TRADING_DAYS.length * chartW;
          const v = avgs[i];
          const y0 = innerH / 2;
          const y1 = yScale(v);
          const bTop = Math.min(y0, y1);
          const bH = Math.abs(y0 - y1);
          const color = v >= 0 ? 'var(--color-up)' : 'var(--color-down)';
          const cnt = dowMap[d]?.length ?? 0;
          return (
            <g key={d}>
              <rect x={x - barW / 2} y={bTop} width={barW} height={Math.max(bH, 1)} fill={color} opacity={0.85} />
              <text x={x} y={innerH + XAXIS_H - 4} fontSize={10} fill="var(--color-muted)" textAnchor="middle">{KR_DAYS[d]}</text>
              {bH > 14 && (
                <text x={x} y={v >= 0 ? bTop - 2 : bTop + bH + 10} fontSize={8} fill={color} textAnchor="middle">
                  {v >= 0 ? '+' : ''}{v.toFixed(2)}%
                </text>
              )}
              {cnt > 0 && bH < 10 && (
                <text x={x} y={innerH - 4} fontSize={8} fill="var(--color-muted)" textAnchor="middle" opacity={0.4}>{cnt}일</text>
              )}
            </g>
          );
        })}
      </svg>
    </div>
  );
}

// ── Modal ──────────────────────────────────────────────────────
function Modal({ onClose, title, children }: { onClose: () => void; title: string; children: React.ReactNode }) {
  useEffect(() => {
    const fn = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', fn);
    return () => window.removeEventListener('keydown', fn);
  }, [onClose]);

  return (
    <div style={{ position: 'fixed', inset: 0, backgroundColor: 'rgba(0,0,0,0.82)', zIndex: 9000, display: 'flex', alignItems: 'center', justifyContent: 'center' }} onClick={onClose}>
      <div style={{ width: 'min(1280px, 96vw)', height: 'min(680px, 90vh)', backgroundColor: 'var(--color-bg)', borderRadius: 12, overflow: 'hidden', position: 'relative', border: '1px solid var(--color-border)', display: 'flex', flexDirection: 'column' }} onClick={e => e.stopPropagation()}>
        <div style={{ padding: '8px 16px', borderBottom: '1px solid var(--color-border)', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexShrink: 0 }}>
          <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--color-text)' }}>{title}</span>
          <button onClick={onClose} style={{ background: 'none', border: '1px solid var(--color-border)', borderRadius: 4, padding: '2px 10px', cursor: 'pointer', fontSize: 13, color: 'var(--color-muted)' }}>✕</button>
        </div>
        <div style={{ flex: 1, overflow: 'hidden' }}>{children}</div>
      </div>
    </div>
  );
}

// ── CandleChart4: 2×2 그리드 ──────────────────────────────────
export default function CandleChart4({ ticker }: { ticker: string }) {
  const [expanded, setExpanded] = useState<QuadKey | null>(null);

  const QUAD_TITLES: Record<QuadKey, string> = {
    q1: '금일 5분봉 (실시간)',
    q2: '시간대별 평균 수익률',
    q3: '요일별 평균 수익률 (90일)',
    q4: '일봉 캔들 차트',
  };

  const cell = (pos: 'tl' | 'tr' | 'bl' | 'br'): CSSProperties => ({
    overflow: 'hidden',
    backgroundColor: 'var(--color-surface)',
    position: 'relative',
    borderRight: pos === 'tl' || pos === 'bl' ? '1px solid var(--color-border)' : undefined,
    borderBottom: pos === 'tl' || pos === 'tr' ? '1px solid var(--color-border)' : undefined,
  });

  return (
    <>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gridTemplateRows: `${QUAD_H}px ${QUAD_H}px`, border: '1px solid var(--color-border)', borderRadius: 8, overflow: 'hidden' }}>
        <div style={cell('tl')}>
          <IntradayLineChart ticker={ticker} onExpand={() => setExpanded('q1')} />
        </div>
        <div style={cell('tr')}>
          <HourlyPatternChart ticker={ticker} onExpand={() => setExpanded('q2')} />
        </div>
        <div style={cell('bl')}>
          <WeekdayPatternChart ticker={ticker} onExpand={() => setExpanded('q3')} />
        </div>
        <div style={cell('br')}>
          <ExpandBtn onClick={() => setExpanded('q4')} />
          <CandleChart ticker={ticker} height={QUAD_H} />
        </div>
      </div>

      {expanded && (
        <Modal onClose={() => setExpanded(null)} title={QUAD_TITLES[expanded]}>
          {expanded === 'q1' && <IntradayLineChart ticker={ticker} height={MODAL_CHART_H} />}
          {expanded === 'q2' && <HourlyPatternChart ticker={ticker} height={MODAL_CHART_H} />}
          {expanded === 'q3' && <WeekdayPatternChart ticker={ticker} height={MODAL_CHART_H} />}
          {expanded === 'q4' && <CandleChart ticker={ticker} height={MODAL_CHART_H} />}
        </Modal>
      )}
    </>
  );
}
