'use client';
import { useState, useEffect } from 'react';

const BFF = process.env.NEXT_PUBLIC_BFF_URL ?? 'http://localhost:3002';

type Fill = { ticker: string; side: string; quantity: number; fill_price: number; fee: number; realized_pnl: number };
type ExecResult = { accepted: boolean; fill: Fill | null; reason: string } | null;

export default function SimulationPanel({ ticker, price }: { ticker: string; price?: number }) {
  const [qtyStr, setQtyStr] = useState('1');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<ExecResult>(null);
  const [err, setErr] = useState('');
  const [cash, setCash] = useState<number | null>(null);

  // 종목 변경 시 수량·결과 초기화
  useEffect(() => {
    setQtyStr('1');
    setResult(null);
    setErr('');
  }, [ticker]);

  // 예수금 잔액 조회
  useEffect(() => {
    fetch(`${BFF}/api/portfolio`, { signal: AbortSignal.timeout(3000) })
      .then((r) => r.ok ? r.json() : null)
      .then((data) => { if (typeof data?.cash === 'number') setCash(data.cash); })
      .catch(() => {});
  }, []);

  const qty = parseInt(qtyStr) || 0;
  const total = qty * (price ?? 0);

  function handleQtyChange(e: React.ChangeEvent<HTMLInputElement>) {
    // 숫자(또는 빈 문자열)만 허용, 앞자리 0 제거
    const raw = e.target.value.replace(/[^0-9]/g, '');
    setQtyStr(raw === '' ? '' : String(parseInt(raw) || 0));
  }

  function handleQtyFocus(e: React.FocusEvent<HTMLInputElement>) {
    e.target.select(); // 포커스 시 전체 선택 → 바로 덮어쓰기
  }

  function handleQtyBlur() {
    setQtyStr(String(qty || 0));
  }

  async function execute(side: 'buy' | 'sell') {
    if (qty === 0) {
      alert('수량을 입력해주세요. (1주 이상)');
      return;
    }
    // 매수 시 예수금 사전 확인
    if (side === 'buy' && cash !== null && total > cash) {
      alert(
        `예수금이 부족합니다.\n필요: ${total.toLocaleString('ko-KR')}원\n잔액: ${cash.toLocaleString('ko-KR')}원`,
      );
      return;
    }

    setLoading(true); setErr(''); setResult(null);
    try {
      const r = await fetch(`${BFF}/api/paper/execute`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ticker, side, quantity: qty, price: price ?? 0 }),
      });
      if (!r.ok) {
        const t = await r.text();
        throw new Error(`${r.status}: ${t.slice(0, 100)}`);
      }
      const data: ExecResult = await r.json();
      setResult(data);
      // 매수 거부 → 예수금 부족 alert (백엔드 최종 판정)
      if (data && !data.accepted && side === 'buy') {
        const reason = (data.reason ?? '').toLowerCase();
        if (reason.includes('cash') || reason.includes('balance') || reason.includes('insufficient') || reason.includes('예수금')) {
          alert('예수금이 부족합니다.');
        }
      }
      // 체결 성공 시 잔액 갱신
      if (data?.accepted) {
        fetch(`${BFF}/api/portfolio`, { signal: AbortSignal.timeout(3000) })
          .then((r) => r.ok ? r.json() : null)
          .then((d) => { if (typeof d?.cash === 'number') setCash(d.cash); })
          .catch(() => {});
      }
    } catch (e) {
      setErr(String(e));
    } finally {
      setLoading(false);
    }
  }

  const overBudget = cash !== null && qty > 0 && price != null && price > 0 && total > cash;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
      {/* 행1: (현재주가) X원  수량 [input]  = Y원 */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11, flexWrap: 'wrap' }}>
        <span style={{ color: 'var(--color-muted)', whiteSpace: 'nowrap' }}>
          (현재주가)&nbsp;<span style={{ fontFamily: 'monospace', color: 'var(--color-text)' }}>{price != null && price > 0 ? price.toLocaleString('ko-KR') + '원' : '-'}</span>
        </span>
        <span style={{ color: 'var(--color-muted)', flexShrink: 0 }}>수량</span>
        <input
          type="number"
          min={0}
          step={1}
          value={qtyStr}
          onChange={handleQtyChange}
          onFocus={handleQtyFocus}
          onBlur={handleQtyBlur}
          style={{ width: 52, padding: '3px 6px', borderRadius: 4, border: '1px solid var(--color-border)', backgroundColor: 'var(--color-bg)', color: 'var(--color-text)', fontSize: 12, flexShrink: 0 }}
        />
        {price != null && price > 0 && qty > 0 && (
          <span style={{ fontFamily: 'monospace', color: overBudget ? 'var(--color-down)' : 'var(--color-muted)', whiteSpace: 'nowrap', fontWeight: overBudget ? 700 : 400 }}>
            = {total.toLocaleString('ko-KR')}
          </span>
        )}
      </div>

      {/* 행2: 예수금  +  매수/매도 버튼 */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
        <span style={{ fontSize: 9, color: 'var(--color-muted)', flex: 1 }}>
          {cash !== null ? `예수금 ${cash.toLocaleString('ko-KR')}원` : ''}
        </span>
        <button
          onClick={() => execute('buy')}
          disabled={loading}
          style={{ padding: '3px 10px', borderRadius: 4, backgroundColor: 'rgba(63,185,80,0.13)', color: 'var(--color-up)', fontWeight: 700, fontSize: 11, cursor: loading ? 'wait' : 'pointer', border: '1px solid rgba(63,185,80,0.3)', outline: 'none', opacity: loading ? 0.7 : 1, flexShrink: 0 }}
        >▲ 매수</button>
        <button
          onClick={() => execute('sell')}
          disabled={loading}
          style={{ padding: '3px 10px', borderRadius: 4, backgroundColor: 'rgba(248,81,73,0.10)', color: 'var(--color-down)', fontWeight: 700, fontSize: 11, cursor: loading ? 'wait' : 'pointer', border: '1px solid rgba(248,81,73,0.25)', outline: 'none', opacity: loading ? 0.7 : 1, flexShrink: 0 }}
        >▼ 매도</button>
      </div>

      {err && (
        <div style={{ fontSize: 11, color: 'var(--color-down)', marginTop: 8 }}>
          ⚠ {err.includes('risk-engine') || err.includes('3001') || err.includes('ECONNREFUSED') || err.startsWith('5') ? err : `${err} — risk-engine(:3001) 기동 필요`}
        </div>
      )}
      {result && result.accepted && result.fill && (
        <div style={{ fontSize: 11, color: 'var(--color-up)', marginTop: 8, lineHeight: 1.6 }}>
          ✓ {result.fill.side === 'buy' ? '매수' : '매도'} 체결<br />
          {result.fill.ticker} · {result.fill.quantity}주 · @{result.fill.fill_price?.toLocaleString('ko-KR')}원
          {result.fill.realized_pnl !== 0 && (
            <span style={{ color: result.fill.realized_pnl > 0 ? 'var(--color-up)' : 'var(--color-down)', marginLeft: 6 }}>
              ({result.fill.realized_pnl > 0 ? '+' : ''}{result.fill.realized_pnl.toFixed(0)}원)
            </span>
          )}
        </div>
      )}
      {result && !result.accepted && (
        <div style={{ fontSize: 11, color: 'var(--color-down)', marginTop: 8 }}>⚠ 거부: {result.reason}</div>
      )}
    </div>
  );
}
