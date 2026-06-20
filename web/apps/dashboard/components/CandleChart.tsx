'use client';

import { useEffect, useRef, useState } from 'react';
import {
  candleLayout,
  applyLivePrice,
  findCandleIndex,
  priceRange,
  scaleY,
  type Candle,
  type CandleResponse,
} from '@/lib/candles';
import { formatPrice } from '@/lib/format';

const BFF_URL = process.env.NEXT_PUBLIC_BFF_URL ?? 'http://localhost:3002';
const POLL_MS = 5_000;
const YAXIS_W = 64;   // Y축 레이블 영역 폭
const XAXIS_H = 22;   // X축 날짜 영역 높이
const DEFAULT_CHART_H = 660;
const MIN_VISIBLE = 10;
const ZOOM_STEP = 5;
const Y_PADDING_RATIO = 0.06; // 상하 여백 비율

interface TooltipState {
  candle: Candle;
  clientX: number;
  clientY: number;
}

// 가격 축 눈금 계산 — 인간 친화적 간격(1,2,2.5,5,10 × 10^n)
function niceYTicks(min: number, max: number, target = 5): number[] {
  const range = max - min;
  if (range <= 0) return [Math.round(min)];
  const rough = range / target;
  const pow = Math.pow(10, Math.floor(Math.log10(rough)));
  const factors = [1, 2, 2.5, 5, 10];
  const interval = (factors.find((f) => f * pow >= rough) ?? 10) * pow;
  const start = Math.ceil(min / interval) * interval;
  const ticks: number[] = [];
  for (let t = start; t <= max + interval * 0.01; t += interval) {
    const v = Math.round(t);
    if (v >= min && v <= max) ticks.push(v);
  }
  return ticks;
}

function formatYLabel(v: number): string {
  if (v >= 1_000_000) return `${(v / 1_000_000).toFixed(1)}M`;
  if (v >= 100_000)   return `${Math.round(v / 1_000)}K`;
  if (v >= 1_000)     return v.toLocaleString('ko-KR');
  return String(v);
}

function formatDateLabel(dateStr: string): string {
  const p = dateStr.split('-');
  return p.length === 3 ? `${p[1]}/${p[2]}` : dateStr.slice(-5);
}

function pickXLabels(candles: Candle[], chartW: number): { x: number; label: string }[] {
  const n = candles.length;
  if (n === 0) return [];
  const slot = chartW / n;
  const maxLabels = Math.max(2, Math.floor(chartW / 60));
  const step = Math.max(1, Math.ceil(n / maxLabels));
  return Array.from({ length: Math.ceil(n / step) }, (_, k) => {
    const i = k * step;
    return { x: i * slot + slot / 2, label: formatDateLabel(candles[i].date) };
  });
}

export default function CandleChart({ ticker, days = 30, height }: { ticker: string; days?: number; height?: number }) {
  const CHART_H = height ?? DEFAULT_CHART_H;
  const [candles, setCandles] = useState<Candle[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [tooltip, setTooltip] = useState<TooltipState | null>(null);
  const [visibleCount, setVisibleCount] = useState(days);
  const [svgWidth, setSvgWidth] = useState(720);
  const containerRef = useRef<HTMLDivElement>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // 컨테이너 폭 추적 — 반응형
  useEffect(() => {
    if (!containerRef.current) return;
    const ro = new ResizeObserver((entries) => {
      const w = entries[0].contentRect.width;
      if (w > 0) setSvgWidth(Math.floor(w));
    });
    ro.observe(containerRef.current);
    return () => ro.disconnect();
  }, []);

  // 데이터 로딩 + 실시간 폴링
  useEffect(() => {
    let alive = true;

    async function loadBars() {
      try {
        const res = await fetch(`${BFF_URL}/api/candles/${ticker}?days=${days}`, { cache: 'no-store' });
        if (!res.ok) throw new Error(`candles ${res.status}`);
        const data: CandleResponse = await res.json();
        if (alive) {
          setCandles(data.bars ?? []);
          setVisibleCount(data.bars?.length ?? days);
          setError(null);
        }
      } catch (e) {
        if (alive) setError(String(e));
      }
    }

    async function pollLive() {
      try {
        const res = await fetch(`${BFF_URL}/api/price/${ticker}`, { cache: 'no-store' });
        if (!res.ok) return;
        const p = await res.json();
        if (alive && typeof p?.price === 'number') {
          setCandles((prev) => applyLivePrice(prev, p.price));
        }
      } catch { /* 폴링 실패는 무시 */ }
    }

    loadBars();
    timerRef.current = setInterval(pollLive, POLL_MS);
    return () => {
      alive = false;
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [ticker, days]);

  // 표시 범위 슬라이스 (가장 최근 N봉)
  const visible = candles.slice(Math.max(0, candles.length - visibleCount));

  // 레이아웃 계산
  const chartW = svgWidth - YAXIS_W;
  const chartH = CHART_H - XAXIS_H;
  const { min: rawMin, max: rawMax } = priceRange(visible);
  const pad = (rawMax - rawMin) * Y_PADDING_RATIO;
  const paddedMin = rawMin - pad;
  const paddedMax = rawMax + pad;

  const rects = candleLayout(visible, chartW, chartH, 2, paddedMin, paddedMax);
  const yTicks = niceYTicks(paddedMin, paddedMax);
  const xLabels = pickXLabels(visible, chartW);

  function handleMouseMove(e: React.MouseEvent<SVGSVGElement>) {
    const rect = e.currentTarget.getBoundingClientRect();
    const scaleX = svgWidth / rect.width;
    const svgX = (e.clientX - rect.left) * scaleX;
    if (svgX > chartW) { setTooltip(null); return; }
    const idx = findCandleIndex(svgX, visible, chartW);
    if (idx >= 0 && idx < visible.length) {
      setTooltip({ candle: visible[idx], clientX: e.clientX, clientY: e.clientY });
    }
  }

  function handleWheel(e: React.WheelEvent<SVGSVGElement>) {
    e.preventDefault();
    // 위로 스크롤 = 줌인(봉 수 감소), 아래로 = 줌아웃(봉 수 증가)
    const delta = e.deltaY > 0 ? ZOOM_STEP : -ZOOM_STEP;
    setVisibleCount((prev) => Math.max(MIN_VISIBLE, Math.min(candles.length, prev + delta)));
  }

  if (error) {
    return (
      <div ref={containerRef} style={{ width: '100%' }}>
        <p style={{ color: 'var(--color-down)', fontSize: 12 }}>
          캔들 데이터 로드 실패 — ingest/BFF 확인 ({error})
        </p>
      </div>
    );
  }

  if (candles.length === 0) {
    return (
      <div
        ref={containerRef}
        style={{
          width: '100%',
          height: CHART_H,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: 'var(--color-muted)',
          fontSize: 13,
          backgroundColor: 'var(--color-surface)',
          borderRadius: 6,
        }}
      >
        캔들 로딩 중…
      </div>
    );
  }

  return (
    <div ref={containerRef} style={{ width: '100%' }}>
      <svg
        width={svgWidth}
        height={CHART_H}
        style={{
          display: 'block',
          backgroundColor: 'var(--color-surface)',
          borderRadius: 6,
          cursor: 'crosshair',
          userSelect: 'none',
        }}
        onMouseMove={handleMouseMove}
        onMouseLeave={() => setTooltip(null)}
        onWheel={handleWheel}
      >
        {/* ── Y gridlines ──────────────────────────────── */}
        {yTicks.map((tick) => {
          const y = scaleY(tick, paddedMin, paddedMax, chartH);
          return (
            <g key={tick}>
              <line
                x1={0} x2={chartW}
                y1={y} y2={y}
                stroke="var(--color-border)"
                strokeWidth={1}
                strokeDasharray="3,4"
              />
              {/* Y축 레이블 */}
              <text
                x={chartW + 4}
                y={y + 4}
                fontSize={10}
                fill="var(--color-muted)"
                textAnchor="start"
              >
                {formatYLabel(tick)}
              </text>
            </g>
          );
        })}

        {/* ── Y axis separator ─────────────────────────── */}
        <line
          x1={chartW} x2={chartW}
          y1={0} y2={chartH}
          stroke="var(--color-border)"
          strokeWidth={1}
        />

        {/* ── X axis baseline ──────────────────────────── */}
        <line
          x1={0} x2={chartW}
          y1={chartH} y2={chartH}
          stroke="var(--color-border)"
          strokeWidth={1}
        />

        {/* ── X axis date labels ───────────────────────── */}
        {xLabels.map(({ x, label }, i) => (
          <text
            key={i}
            x={x}
            y={chartH + 16}
            fontSize={10}
            fill="var(--color-muted)"
            textAnchor="middle"
          >
            {label}
          </text>
        ))}

        {/* ── Candles ──────────────────────────────────── */}
        {rects.map((r, i) => {
          const fill = r.color === 'up' ? 'var(--color-up)' : 'var(--color-down)';
          return (
            <g key={i}>
              <line
                x1={r.wickX} x2={r.wickX}
                y1={r.wickTop} y2={r.wickBottom}
                stroke={fill} strokeWidth={1} opacity={0.85}
              />
              <rect
                x={r.x} y={r.bodyY}
                width={r.width} height={Math.max(r.bodyHeight, 1)}
                fill={fill} opacity={0.9}
              />
            </g>
          );
        })}

        {/* ── 줌 힌트 ──────────────────────────────────── */}
        <text
          x={chartW - 6}
          y={14}
          fontSize={9}
          fill="var(--color-muted)"
          textAnchor="end"
          opacity={0.5}
        >
          스크롤 줌 · {visible.length}봉
        </text>
      </svg>

      {tooltip && <CandleTooltip {...tooltip} />}
    </div>
  );
}

// ── 캔들 상세 툴팁 ─────────────────────────────────────────
const TOOLTIP_W = 168;

function CandleTooltip({ candle, clientX, clientY }: TooltipState) {
  const left =
    typeof window !== 'undefined' && clientX + TOOLTIP_W + 16 > window.innerWidth
      ? clientX - TOOLTIP_W - 8
      : clientX + 14;
  const top = Math.max(8, clientY - 14);

  const change = candle.close - candle.open;
  const changePct = candle.open !== 0 ? (change / candle.open) * 100 : 0;
  const up = change >= 0;

  return (
    <div
      style={{
        position: 'fixed',
        left,
        top,
        width: TOOLTIP_W,
        backgroundColor: 'var(--color-card)',
        border: '1px solid var(--color-border)',
        borderRadius: 6,
        padding: '8px 10px',
        fontSize: 11,
        pointerEvents: 'none',
        zIndex: 9999,
        boxShadow: '0 4px 16px rgba(0,0,0,0.4)',
      }}
    >
      <div style={{ color: 'var(--color-muted)', marginBottom: 6, fontWeight: 600, fontSize: 11 }}>
        {candle.date}
      </div>
      {([ ['O', candle.open], ['H', candle.high], ['L', candle.low], ['C', candle.close] ] as [string, number][]).map(
        ([label, val]) => (
          <div key={label} style={{ display: 'flex', justifyContent: 'space-between', padding: '1px 0' }}>
            <span style={{ color: 'var(--color-muted)' }}>{label}</span>
            <span className="mono" style={{ color: 'var(--color-text)', fontWeight: 600 }}>
              {formatPrice(val)}
            </span>
          </div>
        ),
      )}
      {candle.volume != null && (
        <div
          style={{
            display: 'flex', justifyContent: 'space-between',
            borderTop: '1px solid var(--color-border)', marginTop: 4, paddingTop: 4,
          }}
        >
          <span style={{ color: 'var(--color-muted)' }}>Vol</span>
          <span className="mono" style={{ color: 'var(--color-muted)' }}>
            {candle.volume.toLocaleString()}
          </span>
        </div>
      )}
      <div
        style={{
          textAlign: 'right', marginTop: 4, fontWeight: 700,
          color: up ? 'var(--color-up)' : 'var(--color-down)',
        }}
      >
        {up ? '+' : ''}{change.toFixed(0)} ({up ? '+' : ''}{changePct.toFixed(2)}%)
      </div>
    </div>
  );
}
