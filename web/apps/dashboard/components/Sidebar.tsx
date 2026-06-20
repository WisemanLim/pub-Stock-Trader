'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { Tooltip } from './Tooltip';
import { TOOLTIPS } from '@/lib/tooltips';
import { clearSession, getStoredUser } from '@/lib/auth-client';
import MyPagePanel from './MyPagePanel';

function getCookie(name: string): string | null {
  if (typeof document === 'undefined') return null;
  const match = document.cookie.match(new RegExp('(?:^|; )' + name + '=([^;]*)'));
  return match ? decodeURIComponent(match[1]) : null;
}

const MENU = [
  { href: '/', label: '대시보드', icon: '▦', tooltip: TOOLTIPS.menu.dashboard },
  { href: '/portfolio', label: '포트폴리오', icon: '◈', tooltip: TOOLTIPS.menu.portfolio },
  { href: '/strategy', label: '전략', icon: '◎', tooltip: TOOLTIPS.menu.strategy },
  { href: '/risk', label: '리스크', icon: '⚠', tooltip: TOOLTIPS.menu.risk },
  { href: '/backtest', label: '백테스팅', icon: '↺', tooltip: TOOLTIPS.menu.backtest },
  { href: '/agents', label: '에이전트', icon: '◉', tooltip: TOOLTIPS.menu.agents },
];

const PERSONAS = [
  { value: 'scalper', label: '스캘퍼', tooltip: TOOLTIPS.persona.scalper },
  { value: 'day',     label: '데이',   tooltip: TOOLTIPS.persona.day     },
  { value: 'swing',   label: '스윙',   tooltip: TOOLTIPS.persona.swing   },
  { value: 'position',label: '포지션', tooltip: TOOLTIPS.persona.position},
];

const SERVICES = [
  { label: 'ingest',   tooltip: TOOLTIPS.service.ingest   },
  { label: 'analysis', tooltip: TOOLTIPS.service.analysis },
  { label: 'agents',   tooltip: TOOLTIPS.service.agents   },
  { label: 'risk',     tooltip: TOOLTIPS.service.risk     },
];

export default function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const [myPageOpen, setMyPageOpen] = useState(false);
  const [persona, setPersona] = useState('swing');
  const user = getStoredUser();
  const serviceStatus = useServiceHealth();

  useEffect(() => {
    setPersona(getCookie('st_persona') ?? 'swing');
  }, []);

  function handlePersonaChange(p: string) {
    document.cookie = `st_persona=${encodeURIComponent(p)}; path=/; max-age=2592000`;
    setPersona(p);
    router.push('/');
  }

  function handleLogout() {
    clearSession();
    router.replace('/login');
  }

  return (
    <aside
      style={{
        width: 200,
        minHeight: '100%',
        backgroundColor: 'var(--color-surface)',
        borderRight: '1px solid var(--color-border)',
        display: 'flex',
        flexDirection: 'column',
        padding: '12px 0',
        flexShrink: 0,
        position: 'relative',
      }}
    >
      {/* Navigation */}
      <nav style={{ flex: 1 }}>
        {MENU.map((item) => {
          const active = pathname === item.href;
          return (
            <Tooltip key={item.href} title={item.label} content={item.tooltip} block>
              <Link
                href={item.href}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 10,
                  padding: '9px 16px',
                  color: active ? 'var(--color-accent)' : 'var(--color-muted)',
                  backgroundColor: active ? 'rgba(88,166,255,0.08)' : 'transparent',
                  borderLeft: active ? '2px solid var(--color-accent)' : '2px solid transparent',
                  textDecoration: 'none',
                  fontSize: 13,
                  fontWeight: active ? 600 : 400,
                  transition: 'all 0.15s',
                }}
              >
                <span style={{ fontSize: 15, width: 18, textAlign: 'center' }}>{item.icon}</span>
                {item.label}
              </Link>
            </Tooltip>
          );
        })}
      </nav>

      {/* Persona selector */}
      <div style={{ padding: '12px 16px', borderTop: '1px solid var(--color-border)' }}>
        <Tooltip title="페르소나" content={TOOLTIPS.misc.persona}>
          <span
            style={{
              display: 'block',
              fontSize: 10,
              color: 'var(--color-muted)',
              marginBottom: 8,
              letterSpacing: 1,
              cursor: 'help',
              borderBottom: '1px dotted var(--color-border)',
              paddingBottom: 2,
            }}
          >
            PERSONA
          </span>
        </Tooltip>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          {PERSONAS.map((p) => (
            <Tooltip key={p.value} title={p.label} content={p.tooltip} block>
              <button
                onClick={() => handlePersonaChange(p.value)}
                style={{
                  display: 'block',
                  width: '100%',
                  padding: '5px 8px',
                  borderRadius: 4,
                  fontSize: 12,
                  color: persona === p.value ? 'var(--color-text)' : 'var(--color-muted)',
                  backgroundColor: persona === p.value ? 'var(--color-card)' : 'transparent',
                  border: persona === p.value ? '1px solid var(--color-border)' : '1px solid transparent',
                  cursor: 'pointer',
                  textAlign: 'left',
                }}
              >
                {p.label}
              </button>
            </Tooltip>
          ))}
        </div>
      </div>

      {/* Status indicators */}
      <div
        style={{
          padding: '10px 16px',
          borderTop: '1px solid var(--color-border)',
          display: 'flex',
          flexDirection: 'column',
          gap: 4,
        }}
      >
        {SERVICES.map((s) => (
          <StatusDot key={s.label} label={s.label} tooltip={s.tooltip} up={serviceStatus[s.label]} />
        ))}
      </div>

      {/* User panel */}
      <div style={{ borderTop: '1px solid var(--color-border)', padding: '8px 12px' }}>
        <button
          onClick={() => setMyPageOpen(o => !o)}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 7,
            width: '100%',
            background: 'none',
            border: 'none',
            cursor: 'pointer',
            padding: '4px 0',
            textAlign: 'left',
          }}
        >
          <span style={{
            width: 24, height: 24, borderRadius: '50%',
            backgroundColor: 'var(--color-accent)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 11, color: '#fff', fontWeight: 700, flexShrink: 0,
          }}>
            {user?.name?.charAt(0)?.toUpperCase() ?? '?'}
          </span>
          <span style={{ fontSize: 11, color: 'var(--color-text)', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {user?.name ?? '게스트'}
          </span>
          <span style={{ fontSize: 10, color: 'var(--color-muted)' }}>⚙</span>
        </button>
        <button
          onClick={handleLogout}
          style={{
            marginTop: 4, width: '100%', padding: '4px 0',
            background: 'none', border: 'none', cursor: 'pointer',
            fontSize: 10, color: 'var(--color-muted)', textAlign: 'left',
          }}
        >
          ⎋ 로그아웃
        </button>
      </div>

      {myPageOpen && <MyPagePanel onClose={() => setMyPageOpen(false)} />}
    </aside>
  );
}

// 서비스 헬스 상태 — 주식 색상 변수와 독립된 절대 색상 사용
const STATUS_COLOR = {
  unknown: '#6e7681',  // 회색 (초기/로딩)
  up:      '#3fb950',  // 초록 (정상)
  down:    '#f85149',  // 적색 (다운)
} as const;

const BFF_URL = typeof window !== 'undefined'
  ? (process.env.NEXT_PUBLIC_BFF_URL ?? 'http://localhost:3002')
  : 'http://localhost:3002';

type ServiceStatus = Record<string, boolean | undefined>;

function useServiceHealth() {
  const [status, setStatus] = useState<ServiceStatus>({});

  useEffect(() => {
    async function check() {
      try {
        const r = await fetch(`${BFF_URL}/api/services/health`, {
          signal: AbortSignal.timeout(5000),
          cache: 'no-store',
        });
        if (r.ok) setStatus(await r.json() as ServiceStatus);
        else setStatus({});
      } catch {
        setStatus({});
      }
    }
    check();
    const id = setInterval(check, 30_000);
    return () => clearInterval(id);
  }, []);

  return status;
}

function StatusDot({ label, tooltip, up }: { label: string; tooltip: string; up: boolean | undefined }) {
  const color = up === undefined ? STATUS_COLOR.unknown : up ? STATUS_COLOR.up : STATUS_COLOR.down;
  const hint  = up === undefined ? '확인 중…' : up ? '정상' : '연결 불가';
  return (
    <Tooltip title={label} content={`${tooltip} — ${hint}`} block>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11, cursor: 'help' }}>
        <span style={{ width: 6, height: 6, borderRadius: '50%', backgroundColor: color, display: 'inline-block', flexShrink: 0 }} />
        <span style={{ color: 'var(--color-muted)' }}>{label}</span>
      </div>
    </Tooltip>
  );
}
