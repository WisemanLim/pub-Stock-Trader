'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import {
  storeSession, getToken, getAutoLoginPref, saveAutoLoginPref,
  getRememberedEmail, saveRememberEmail, clearRememberEmail,
  saveEncryptedCreds, loadEncryptedCreds, clearEncryptedCreds,
} from '@/lib/auth-client';

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [totpCode, setTotpCode] = useState('');
  const [totpRequired, setTotpRequired] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [rememberEmail, setRememberEmail] = useState(false);
  const [autoLogin, setAutoLogin] = useState(true);
  const [autoLoginAttempting, setAutoLoginAttempting] = useState(false);

  useEffect(() => {
    if (getToken()) { router.replace('/'); return; }
    const saved = getRememberedEmail();
    if (saved) { setEmail(saved); setRememberEmail(true); }
    const autoPref = getAutoLoginPref();
    setAutoLogin(autoPref);

    // 자동로그인: 저장된 암호화 자격증명으로 자동 로그인 시도
    if (autoPref) {
      setAutoLoginAttempting(true);
      loadEncryptedCreds().then(async (creds) => {
        if (!creds) { setAutoLoginAttempting(false); return; }
        try {
          const res = await fetch('/api/auth/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email: creds.email, password: creds.password }),
          });
          const data = await res.json();
          if (res.ok && !data.totp_required) {
            storeSession(data.token, data.user, true);
            router.replace('/');
          } else {
            // 비밀번호 변경 등 — 저장 자격증명 무효화, 폼 표시
            clearEncryptedCreds();
            setEmail(creds.email);
            setAutoLoginAttempting(false);
          }
        } catch {
          setAutoLoginAttempting(false);
        }
      });
    }
  }, [router]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const res = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password, totp_code: totpCode || undefined }),
      });
      const data = await res.json();
      if (!res.ok) {
        if (data.totp_required) setTotpRequired(true);
        setError(data.error);
        return;
      }
      if (rememberEmail) saveRememberEmail(email);
      else clearRememberEmail();
      saveAutoLoginPref(autoLogin);
      // 자동로그인 체크 시 암호화 자격증명 저장, 해제 시 삭제
      if (autoLogin) await saveEncryptedCreds(email, password);
      else clearEncryptedCreds();
      storeSession(data.token, data.user, autoLogin);
      router.replace('/');
    } catch {
      setError('서버 오류가 발생했습니다.');
    } finally {
      setLoading(false);
    }
  }

  if (autoLoginAttempting) {
    return (
      <div style={{
        minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center',
        backgroundColor: 'var(--color-bg)', flexDirection: 'column', gap: 12,
      }}>
        <div style={{ fontSize: 13, color: 'var(--color-muted)' }}>자동 로그인 중…</div>
      </div>
    );
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
        width: 360,
        backgroundColor: 'var(--color-surface)',
        border: '1px solid var(--color-border)',
        borderRadius: 8,
        padding: '32px 28px',
      }}>
        <div style={{ marginBottom: 24 }}>
          <div style={{ fontSize: 22, fontWeight: 700, color: 'var(--color-text)', marginBottom: 4 }}>
            Stock Trader
          </div>
          <div style={{ fontSize: 13, color: 'var(--color-muted)' }}>로그인</div>
        </div>

        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <Field label="이메일">
            <input
              type="email"
              value={email}
              onChange={e => setEmail(e.target.value)}
              required
              autoFocus={!email}
              placeholder="user@example.com"
              style={inputStyle}
            />
          </Field>

          <Field label="비밀번호">
            <input
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              required
              placeholder="••••••••"
              style={inputStyle}
            />
          </Field>

          {totpRequired && (
            <Field label="TOTP 코드">
              <input
                type="text"
                value={totpCode}
                onChange={e => setTotpCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                placeholder="6자리 코드"
                maxLength={6}
                autoFocus
                style={inputStyle}
              />
            </Field>
          )}

          {/* 아이디 기억하기 + 자동로그인 */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <CheckOption
              label="아이디 기억하기"
              checked={rememberEmail}
              onChange={setRememberEmail}
            />
            <CheckOption
              label="자동로그인"
              checked={autoLogin}
              onChange={setAutoLogin}
            />
          </div>

          {error && (
            <div style={{ fontSize: 12, color: 'var(--color-down)', padding: '6px 10px', backgroundColor: 'rgba(255,82,82,0.08)', borderRadius: 4 }}>
              {error}
            </div>
          )}

          <button type="submit" disabled={loading} style={btnStyle}>
            {loading ? '로그인 중...' : '로그인'}
          </button>
        </form>

        <div style={{ marginTop: 20, textAlign: 'center', fontSize: 12, color: 'var(--color-muted)' }}>
          계정이 없으신가요?{' '}
          <a href="/register" style={{ color: 'var(--color-accent)', textDecoration: 'none' }}>
            회원가입
          </a>
        </div>
      </div>
    </div>
  );
}

function CheckOption({ label, checked, onChange }: { label: string; checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <label style={{ display: 'flex', alignItems: 'center', gap: 5, cursor: 'pointer', fontSize: 12, color: 'var(--color-muted)', userSelect: 'none' }}>
      <input
        type="checkbox"
        checked={checked}
        onChange={e => onChange(e.target.checked)}
        style={{ accentColor: 'var(--color-accent)', width: 14, height: 14 }}
      />
      {label}
    </label>
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
  marginTop: 4,
};
