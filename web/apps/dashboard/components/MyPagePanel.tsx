'use client';

import { useState, useEffect } from 'react';
import { getToken, getStoredUser, updateStoredUser } from '@/lib/auth-client';

type Tab = 'password' | 'cash' | 'totp';

interface Props {
  onClose: () => void;
}

export default function MyPagePanel({ onClose }: Props) {
  const [tab, setTab] = useState<Tab>('password');

  return (
    <div
      style={{
        position: 'absolute',
        bottom: 0,
        left: 0,
        right: 0,
        backgroundColor: 'var(--color-surface)',
        border: '1px solid var(--color-border)',
        borderBottom: 'none',
        borderRadius: '6px 6px 0 0',
        zIndex: 100,
        display: 'flex',
        flexDirection: 'column',
        boxShadow: '0 -4px 16px rgba(0,0,0,0.4)',
      }}
    >
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', padding: '10px 14px 0', gap: 8 }}>
        <span style={{ flex: 1, fontSize: 12, fontWeight: 600, color: 'var(--color-text)' }}>마이페이지</span>
        <button onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--color-muted)', fontSize: 14 }}>✕</button>
      </div>

      {/* Tabs */}
      <div style={{ display: 'flex', borderBottom: '1px solid var(--color-border)', margin: '8px 14px 0' }}>
        {(['password', 'cash', 'totp'] as Tab[]).map(t => (
          <button
            key={t}
            onClick={() => setTab(t)}
            style={{
              padding: '5px 10px',
              fontSize: 11,
              border: 'none',
              borderBottom: tab === t ? '2px solid var(--color-accent)' : '2px solid transparent',
              background: 'none',
              cursor: 'pointer',
              color: tab === t ? 'var(--color-accent)' : 'var(--color-muted)',
              fontWeight: tab === t ? 600 : 400,
            }}
          >
            {t === 'password' ? '비밀번호' : t === 'cash' ? '예수금' : 'TOTP'}
          </button>
        ))}
      </div>

      {/* Content */}
      <div style={{ padding: '12px 14px 14px' }}>
        {tab === 'password' && <PasswordTab />}
        {tab === 'cash' && <CashTab onClose={onClose} />}
        {tab === 'totp' && <TotpTab />}
      </div>
    </div>
  );
}

function PasswordTab() {
  const [cur, setCur] = useState('');
  const [next, setNext] = useState('');
  const [msg, setMsg] = useState('');
  const [err, setErr] = useState('');
  const [loading, setLoading] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (next.length < 8) { setErr('새 비밀번호 8자 이상'); return; }
    setLoading(true); setErr(''); setMsg('');
    const res = await fetch('/api/auth/change-password', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${getToken()}` },
      body: JSON.stringify({ current_password: cur, new_password: next }),
    });
    const data = await res.json();
    if (!res.ok) setErr(data.error);
    else { setMsg('변경되었습니다.'); setCur(''); setNext(''); }
    setLoading(false);
  }

  return (
    <form onSubmit={submit} style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      <SmallInput label="현재 비밀번호" type="password" value={cur} onChange={setCur} />
      <SmallInput label="새 비밀번호" type="password" value={next} onChange={setNext} />
      {err && <div style={errStyle}>{err}</div>}
      {msg && <div style={okStyle}>{msg}</div>}
      <SmallBtn disabled={loading}>{loading ? '처리 중...' : '변경'}</SmallBtn>
    </form>
  );
}

function CashTab({ onClose: _onClose }: { onClose: () => void }) {
  const user = getStoredUser();
  const [cash, setCash] = useState(String(user?.initial_cash ?? 100000000));
  const [msg, setMsg] = useState('');
  const [err, setErr] = useState('');
  const [loading, setLoading] = useState(false);
  const [totalBuy, setTotalBuy] = useState<number>(0);

  // 매수총금액(cost_basis 합) + 잔여예수금 → 초기 예수금 역산
  useEffect(() => {
    const BFF = process.env.NEXT_PUBLIC_BFF_URL ?? 'http://localhost:3002';
    fetch(`${BFF}/api/portfolio`, { signal: AbortSignal.timeout(3000) })
      .then((r) => r.ok ? r.json() : null)
      .then((data) => {
        if (!data) return;
        const total = Array.isArray(data.positions)
          ? (data.positions as Array<{ cost_basis?: number; avg_price: number; quantity: number }>)
              .reduce((sum, p) => sum + (p.cost_basis ?? p.avg_price * (p.quantity ?? 0)), 0)
          : 0;
        setTotalBuy(Math.ceil(total));
        // 초기 예수금 = 잔여예수금 + 매수총금액
        if (typeof data.cash === 'number') {
          setCash(String(Math.round(data.cash + total)));
        }
      })
      .catch(() => {});
  }, []);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    let val = parseInt(cash.replace(/,/g, ''), 10);
    if (!val || val < 0) { setErr('유효한 금액 입력'); return; }
    // 매수총금액보다 작으면 매수총금액으로 자동 조정
    if (totalBuy > 0 && val < totalBuy) {
      val = totalBuy;
      setCash(String(val));
      setMsg(`매수총금액(${totalBuy.toLocaleString('ko-KR')}원) 이상으로 자동 조정되었습니다.`);
    }
    setLoading(true); setErr('');
    const res = await fetch('/api/auth/change-cash', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${getToken()}` },
      body: JSON.stringify({ initial_cash: val }),
    });
    const data = await res.json();
    if (!res.ok) { setErr(data.error); setMsg(''); }
    else {
      updateStoredUser({ initial_cash: val });
      setMsg((prev) => prev || '예수금이 변경되었습니다.');
    }
    setLoading(false);
  }

  return (
    <form onSubmit={submit} style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      <SmallInput
        label="초기 예수금 설정 (KRW)"
        type="text"
        value={Number(cash.replace(/,/g, '') || 0).toLocaleString()}
        onChange={v => setCash(v.replace(/,/g, ''))}
      />
      {totalBuy > 0 && (() => {
        const initial = parseInt(cash.replace(/,/g, ''), 10) || 0;
        const remaining = initial - totalBuy;
        return (
          <div style={{ fontSize: 10, color: 'var(--color-muted)', lineHeight: 1.6 }}>
            매수총금액: {totalBuy.toLocaleString('ko-KR')}원<br />
            변경 후 잔여예수금: <span style={{ color: remaining >= 0 ? 'var(--color-up)' : 'var(--color-down)', fontWeight: 600 }}>
              {remaining.toLocaleString('ko-KR')}원
            </span>
          </div>
        );
      })()}
      {err && <div style={errStyle}>{err}</div>}
      {msg && <div style={okStyle}>{msg}</div>}
      <SmallBtn disabled={loading}>{loading ? '처리 중...' : '변경'}</SmallBtn>
    </form>
  );
}

function TotpTab() {
  const [qr, setQr] = useState('');
  const [secret, setSecret] = useState('');
  const [code, setCode] = useState('');
  const [msg, setMsg] = useState('');
  const [err, setErr] = useState('');
  const [loading, setLoading] = useState(false);

  async function loadQr() {
    setErr(''); setLoading(true);
    const res = await fetch('/api/auth/totp/qr', {
      headers: { Authorization: `Bearer ${getToken()}` },
    });
    const data = await res.json();
    if (!res.ok) setErr(data.error);
    else { setQr(data.qr); setSecret(data.secret); }
    setLoading(false);
  }

  async function enable(e: React.FormEvent) {
    e.preventDefault();
    setErr(''); setLoading(true);
    const res = await fetch('/api/auth/totp/enable', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${getToken()}` },
      body: JSON.stringify({ code }),
    });
    const data = await res.json();
    if (!res.ok) setErr(data.error);
    else { setMsg('TOTP가 활성화되었습니다.'); setQr(''); setSecret(''); setCode(''); }
    setLoading(false);
  }

  if (msg) return <div style={okStyle}>{msg}</div>;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      {!qr ? (
        <SmallBtn onClick={loadQr} disabled={loading}>{loading ? '로딩 중...' : 'QR 코드 생성'}</SmallBtn>
      ) : (
        <>
          <div style={{ textAlign: 'center' }}>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={qr} alt="TOTP QR" style={{ width: 140, height: 140, border: '1px solid var(--color-border)', borderRadius: 4 }} />
          </div>
          <div style={{ fontSize: 9, color: 'var(--color-muted)', textAlign: 'center', wordBreak: 'break-all' }}>{secret}</div>
          <form onSubmit={enable} style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            <SmallInput
              label="TOTP 코드 (6자리)"
              type="text"
              value={code}
              onChange={v => setCode(v.replace(/\D/g, '').slice(0, 6))}
            />
            {err && <div style={errStyle}>{err}</div>}
            <SmallBtn disabled={loading || code.length !== 6}>{loading ? '확인 중...' : '활성화'}</SmallBtn>
          </form>
        </>
      )}
      {err && !qr && <div style={errStyle}>{err}</div>}
    </div>
  );
}

function SmallInput({
  label, type, value, onChange,
}: { label: string; type: string; value: string; onChange: (v: string) => void }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
      <label style={{ fontSize: 10, color: 'var(--color-muted)' }}>{label}</label>
      <input
        type={type}
        value={value}
        onChange={e => onChange(e.target.value)}
        style={{
          padding: '6px 8px',
          borderRadius: 4,
          border: '1px solid var(--color-border)',
          backgroundColor: 'var(--color-bg)',
          color: 'var(--color-text)',
          fontSize: 12,
          outline: 'none',
        }}
      />
    </div>
  );
}

function SmallBtn({
  children, disabled, onClick,
}: { children: React.ReactNode; disabled?: boolean; onClick?: () => void }) {
  return (
    <button
      type={onClick ? 'button' : 'submit'}
      onClick={onClick}
      disabled={disabled}
      style={{
        padding: '7px',
        borderRadius: 4,
        border: 'none',
        backgroundColor: disabled ? 'var(--color-border)' : 'var(--color-accent)',
        color: '#fff',
        fontSize: 12,
        fontWeight: 600,
        cursor: disabled ? 'default' : 'pointer',
      }}
    >
      {children}
    </button>
  );
}

const errStyle: React.CSSProperties = {
  fontSize: 11,
  color: 'var(--color-down)',
  padding: '4px 8px',
  backgroundColor: 'rgba(255,82,82,0.08)',
  borderRadius: 3,
};

const okStyle: React.CSSProperties = {
  fontSize: 11,
  color: 'var(--color-up)',
  padding: '4px 8px',
  backgroundColor: 'rgba(63,185,80,0.08)',
  borderRadius: 3,
};
