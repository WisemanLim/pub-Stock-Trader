'use client';

import { useState, useRef, useEffect, useCallback } from 'react';
import type { ReactNode } from 'react';

export interface TooltipProps {
  /** 툴팁 상단 굵은 제목 (선택) */
  title?: string;
  /** 툴팁 본문. \n = 줄바꿈 */
  content: string;
  children: ReactNode;
  /** hover 후 표시까지의 지연(ms), 기본 260 */
  delay?: number;
  /** 래퍼를 span 대신 div(block)로 렌더링 */
  block?: boolean;
}

const TOOLTIP_W = 280;
const PADDING = 8; // 뷰포트 경계 최소 여백

export function Tooltip({ title, content, children, delay = 260, block = false }: TooltipProps) {
  const [visible, setVisible] = useState(false);
  const [pos, setPos] = useState({ x: 0, y: 0 });
  const posRef = useRef({ x: 0, y: 0 });
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const tooltipRef = useRef<HTMLDivElement>(null);
  const [tooltipH, setTooltipH] = useState(0);

  function onEnter(e: React.MouseEvent) {
    posRef.current = { x: e.clientX, y: e.clientY };
    timer.current = setTimeout(() => {
      setPos(posRef.current);
      setVisible(true);
    }, delay);
  }

  function onLeave() {
    if (timer.current) clearTimeout(timer.current);
    setVisible(false);
    setTooltipH(0);
  }

  function onMove(e: React.MouseEvent) {
    posRef.current = { x: e.clientX, y: e.clientY };
    if (visible) setPos({ x: e.clientX, y: e.clientY });
  }

  // 렌더 후 실제 높이 측정 → 다음 위치 계산에 활용
  useEffect(() => {
    if (visible && tooltipRef.current) {
      setTooltipH(tooltipRef.current.getBoundingClientRect().height);
    }
  }, [visible, pos.x, pos.y]);

  useEffect(() => () => { if (timer.current) clearTimeout(timer.current); }, []);

  const calcPos = useCallback(() => {
    if (typeof window === 'undefined') return { left: 0, top: 0 };
    const vw = window.innerWidth;
    const vh = window.innerHeight;
    const h = tooltipH || 200; // 첫 렌더 fallback

    // 좌우 flip
    const left =
      pos.x + TOOLTIP_W + 16 > vw
        ? Math.max(PADDING, pos.x - TOOLTIP_W - 8)
        : pos.x + 14;

    // 상하 flip: 커서 아래에 맞지 않으면 위로
    const below = pos.y + 14 + h + PADDING;
    const top =
      below > vh
        ? Math.max(PADDING, pos.y - h - 8)   // 커서 위에 표시
        : Math.max(PADDING, pos.y - 14);       // 커서 아래에 표시

    return { left, top };
  }, [pos.x, pos.y, tooltipH]);

  const { left, top } = calcPos();
  const handlers = { onMouseEnter: onEnter, onMouseLeave: onLeave, onMouseMove: onMove };

  return (
    <>
      {block ? (
        <div {...handlers} style={{ display: 'block' }}>
          {children}
        </div>
      ) : (
        <span {...handlers} style={{ display: 'inline' }}>
          {children}
        </span>
      )}

      {visible && (
        <div
          ref={tooltipRef}
          style={{
            position: 'fixed',
            left,
            top,
            width: TOOLTIP_W,
            backgroundColor: 'var(--color-card)',
            border: '1px solid var(--color-border)',
            borderRadius: 8,
            padding: '10px 12px',
            fontSize: 11,
            lineHeight: 1.65,
            pointerEvents: 'none',
            zIndex: 9999,
            boxShadow: '0 6px 24px rgba(0,0,0,0.5)',
          }}
        >
          {title && (
            <div
              style={{
                fontWeight: 700,
                color: 'var(--color-text)',
                fontSize: 12,
                borderBottom: '1px solid var(--color-border)',
                paddingBottom: 5,
                marginBottom: 6,
              }}
            >
              {title}
            </div>
          )}
          <div style={{ color: 'var(--color-muted)' }}>
            {content.split('\n').map((line, i) =>
              line === '' ? (
                <div key={i} style={{ height: 5 }} />
              ) : (
                <div key={i}>{line}</div>
              )
            )}
          </div>
        </div>
      )}
    </>
  );
}
