'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { storeSession } from '@/lib/auth-client';

type Step = 'form' | 'totp';

export default function RegisterPage() {
  const router = useRouter();
  const [step, setStep] = useState<Step>('form');

  const [email, setEmail] = useState('');
  const [name, setName] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [initialCash, setInitialCash] = useState('100000000');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  // TOTP step
  const [qrDataUrl, setQrDataUrl] = useState('');
  const [totpSecret, setTotpSecret] = useState('');
  const [totpCode, setTotpCode] = useState('');
  const [pendingToken, setPendingToken] = useState('');
  const [pendingUser, setPendingUser] = useState<{ id: string; email: string; name: string; initial_cash: number } | null>(null);

  useEffect(() => {
    const token = localStorage.getItem('st_token');
    if (token) router.replace('/');
  }, [router]);

  async function handleRegister(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    if (password !== confirm) {
      setError('비밀번호가 일치하지 않습니다.');
      return;
    }
    const cash = Math.floor(Number(initialCash));
    if (!cash || cash <= 0 || !isFinite(cash)) {
      setError('유효한 예수금을 입력하세요.');
      return;
    }
    setLoading(true);
    try {
      const res = await fetch('/api/auth/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, name, password, initial_cash: cash }),
      });
      const data = await res.json();
      if (!res.ok) { setError(data.error); return; }
      setQrDataUrl(data.totp.qr);
      setTotpSecret(data.totp.secret);
      setPendingToken(data.token);
      setPendingUser(data.user);
      setStep('totp');
    } catch {
      setError('서버 오류가 발생했습니다.');
    } finally {
      setLoading(false);
    }
  }

  async function handleTotpEnable(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const res = await fetch('/api/auth/totp/enable', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${pendingToken}`,
        },
        body: JSON.stringify({ code: totpCode }),
      });
      const data = await res.json();
      if (!res.ok) { setError(data.error); return; }
      storeSession(pendingToken, pendingUser!);
      router.replace('/');
    } catch {
      setError('서버 오류가 발생했습니다.');
    } finally {
      setLoading(false);
    }
  }

  async function skipTotp() {
    storeSession(pendingToken, pendingUser!);
    router.replace('/');
  }

  return (
    <div style={{
      minHeight: '100vh',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      backgroundColor: 'var(--color-bg)',
    }}>
      <div style={{
        width: 400,
        backgroundColor: 'var(--color-surface)',
        border: '1px solid var(--color-border)',
        borderRadius: 8,
        padding: '32px 28px',
      }}>
        <div style={{ marginBottom: 24 }}>
          <div style={{ fontSize: 22, fontWeight: 700, color: 'var(--color-text)', marginBottom: 4 }}>
            Stock Trader
          </div>
          <div style={{ fontSize: 13, color: 'var(--color-muted)' }}>
            {step === 'form' ? '회원가입' : 'TOTP 인증 설정'}
          </div>
        </div>

        {step === 'form' && (
          <form onSubmit={handleRegister} style={{ display: 'flex', flexDirection: 'column', gap: 13 }}>
            <Field label="이메일">
              <input type="email" value={email} onChange={e => setEmail(e.target.value)} required autoFocus placeholder="user@example.com" style={inputStyle} />
            </Field>
            <Field label="성명">
              <input type="text" value={name} onChange={e => setName(e.target.value)} required placeholder="홍길동" style={inputStyle} />
            </Field>
            <Field label="비밀번호">
              <input type="password" value={password} onChange={e => setPassword(e.target.value)} required placeholder="8자 이상" style={inputStyle} />
            </Field>
            <Field label="비밀번호 확인">
              <input type="password" value={confirm} onChange={e => setConfirm(e.target.value)} required placeholder="••••••••" style={inputStyle} />
            </Field>
            <Field label="예수금 (KRW)">
              <input
                type="number"
                value={initialCash}
                onChange={e => setInitialCash(e.target.value)}
                min="1000000"
                step="1000000"
                placeholder="100000000"
                style={inputStyle}
              />
              <span style={{ fontSize: 10, color: 'var(--color-muted)' }}>
                {initialCash ? `= ${Number(initialCash).toLocaleString('ko-KR')} 원` : '기본값: 1억 원'}
              </span>
            </Field>

            {error && <ErrBox msg={error} />}

            <button type="submit" disabled={loading} style={btnStyle}>
              {loading ? '처리 중...' : '다음 (TOTP 설정)'}
            </button>
          </form>
        )}

        {step === 'totp' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <p style={{ fontSize: 12, color: 'var(--color-muted)', margin: 0 }}>
              Google Authenticator 또는 호환 앱으로 QR을 스캔한 후 6자리 코드를 입력하세요.
            </p>
            {qrDataUrl && (
              <div style={{ textAlign: 'center' }}>
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={qrDataUrl} alt="TOTP QR Code" style={{ width: 180, height: 180, border: '1px solid var(--color-border)', borderRadius: 4 }} />
              </div>
            )}
            <div style={{ fontSize: 10, color: 'var(--color-muted)', textAlign: 'center', wordBreak: 'break-all' }}>
              수동 입력: {totpSecret}
            </div>
            <form onSubmit={handleTotpEnable} style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              <Field label="TOTP 코드 (6자리)">
                <input
                  type="text"
                  value={totpCode}
                  onChange={e => setTotpCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                  placeholder="000000"
                  maxLength={6}
                  autoFocus
                  style={{ ...inputStyle, textAlign: 'center', letterSpacing: 6, fontSize: 18 }}
                />
              </Field>
              {error && <ErrBox msg={error} />}
              <button type="submit" disabled={loading || totpCode.length !== 6} style={btnStyle}>
                {loading ? '확인 중...' : 'TOTP 활성화 및 로그인'}
              </button>
            </form>
            <button onClick={skipTotp} style={{ ...btnStyle, backgroundColor: 'transparent', border: '1px solid var(--color-border)', color: 'var(--color-muted)' }}>
              나중에 설정
            </button>
          </div>
        )}

        {step === 'form' && (
          <div style={{ marginTop: 20, textAlign: 'center', fontSize: 12, color: 'var(--color-muted)' }}>
            이미 계정이 있으신가요?{' '}
            <a href="/login" style={{ color: 'var(--color-accent)', textDecoration: 'none' }}>로그인</a>
          </div>
        )}
      </div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
      <label style={{ fontSize: 11, color: 'var(--color-muted)', fontWeight: 500 }}>{label}</label>
      {children}
    </div>
  );
}

function ErrBox({ msg }: { msg: string }) {
  return (
    <div style={{ fontSize: 12, color: 'var(--color-down)', padding: '6px 10px', backgroundColor: 'rgba(255,82,82,0.08)', borderRadius: 4 }}>
      {msg}
    </div>
  );
}

const inputStyle: React.CSSProperties = {
  padding: '8px 10px',
  borderRadius: 5,
  border: '1px solid var(--color-border)',
  backgroundColor: 'var(--color-bg)',
  color: 'var(--color-text)',
  fontSize: 13,
  outline: 'none',
  width: '100%',
  boxSizing: 'border-box',
};

const btnStyle: React.CSSProperties = {
  padding: '10px',
  borderRadius: 5,
  border: 'none',
  backgroundColor: 'var(--color-accent)',
  color: '#fff',
  fontSize: 13,
  fontWeight: 600,
  cursor: 'pointer',
};
