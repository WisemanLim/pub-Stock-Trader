'use client';

import { useRouter } from 'next/navigation';
import { useEffect, useRef, useState, useCallback } from 'react';
import { useTheme } from './ThemeProvider';
import { searchStocks } from '@/lib/stocks';
import type { StockEntry } from '@/lib/stocks';
import { getStoredUser } from '@/lib/auth-client';

// ── 조회 히스토리 (사용자별 localStorage) ──────────────────────────
type HistoryEntry = { ticker: string; name: string };
const HISTORY_MAX = 10;

function historyKey(userId: string) { return `st_ticker_history_${userId}`; }

function loadHistory(userId: string): HistoryEntry[] {
  try {
    const raw = localStorage.getItem(historyKey(userId));
    return raw ? (JSON.parse(raw) as HistoryEntry[]) : [];
  } catch { return []; }
}

function upsertHistory(userId: string, entry: HistoryEntry): HistoryEntry[] {
  const next = [entry, ...loadHistory(userId).filter((h) => h.ticker !== entry.ticker)].slice(0, HISTORY_MAX);
  localStorage.setItem(historyKey(userId), JSON.stringify(next));
  return next;
}

function deleteHistoryItem(userId: string, ticker: string): HistoryEntry[] {
  const next = loadHistory(userId).filter((h) => h.ticker !== ticker);
  localStorage.setItem(historyKey(userId), JSON.stringify(next));
  return next;
}

function clearAllHistory(userId: string): void {
  localStorage.removeItem(historyKey(userId));
}

const INDICES = [
  { label: 'KOSPI',  value: '8,995.85', change: '+1.48%', up: true  },
  { label: 'KOSDAQ', value: '1,003.73', change: '-2.74%', up: false },
  { label: 'KRX300', value: '6,272.44', change: '+1.86%', up: true  },
];

export default function TopBar() {
  const router = useRouter();
  const [input, setInput] = useState('005930');
  const [suggestions, setSuggestions] = useState<StockEntry[]>([]);
  const [activeIdx, setActiveIdx] = useState(-1);
  const [open, setOpen] = useState(false);
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [userId, setUserId] = useState('');
  const persona = 'swing';
  const { theme, toggle } = useTheme();
  const closeTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // 상단 종목 표시: 코드+기업명. localStorage로 서브페이지에서도 유지.
  // 반드시 useEffect 안에서만 localStorage 접근 (SSR 안전).
  const [mounted, setMounted] = useState(false);
  const [displayTicker, setDisplayTicker] = useState('');
  const [displayName, setDisplayName] = useState('');

  useEffect(() => {
    setMounted(true);
    const t = localStorage.getItem('st_ticker') ?? '005930';
    setInput(t);
    setDisplayTicker(t);
    // 로컬 정적 리스트 우선
    const local = searchStocks(t, 1).find((s) => s.ticker === t);
    const savedName = localStorage.getItem('st_name') ?? '';
    const n = local?.name ?? savedName;
    setDisplayName(n);
    // 정적 리스트에 없을 때 BFF로 이름 조회
    if (!n && /^\d{6}$/.test(t)) {
      fetch(`/api/stocks/${t}`, { signal: AbortSignal.timeout(2000) })
        .then((r) => (r.ok ? r.json() : null))
        .then((data) => { if (data?.found && data.name) setDisplayName(data.name as string); })
        .catch(() => {});
    }
    // 사용자별 히스토리 로드
    const user = getStoredUser();
    const uid = user?.id ?? '';
    setUserId(uid);
    if (uid) setHistory(loadHistory(uid));
  }, []);

  const navigate = useCallback(
    (ticker: string) => {
      if (!ticker) return;
      // URL 파라미터 노출 없이 쿠키로 ticker/persona 전달 후 홈 이동
      document.cookie = `st_ticker=${encodeURIComponent(ticker)}; path=/; max-age=2592000`;
      document.cookie = `st_persona=${encodeURIComponent(persona)}; path=/; max-age=2592000`;
      router.push('/');
    },
    [router, persona],
  );

  async function handleChange(val: string) {
    setInput(val);
    setActiveIdx(-1);

    // 빈 입력: 히스토리 드롭다운 표시
    if (!val.trim()) {
      setSuggestions([]);
      setOpen(history.length > 0);
      return;
    }

    // 로컬 즉시 표시
    const local = searchStocks(val);
    setSuggestions(local);
    setOpen(local.length > 0);

    // BFF 동적 검색 (로컬에 없을 때 보완)
    if (val.trim().length >= 2) {
      try {
        const res = await fetch(
          `/api/stocks/search?q=${encodeURIComponent(val.trim())}&limit=8`,
          { signal: AbortSignal.timeout(2000) },
        );
        if (res.ok) {
          const data = await res.json();
          const remote: StockEntry[] = (data.results ?? []).map(
            (r: { ticker: string; name: string; market: string }) => ({
              ticker: r.ticker,
              name: r.name,
              market: r.market as 'KOSPI' | 'KOSDAQ',
            }),
          );
          if (remote.length > 0) {
            setSuggestions(remote);
            setOpen(true);
          }
        }
      } catch { /* BFF 미기동 시 로컬 결과 유지 */ }
    }
  }

  function persistHistory(ticker: string, name: string) {
    if (!userId) return;
    const next = upsertHistory(userId, { ticker, name });
    setHistory(next);
  }

  function handleSelect(entry: StockEntry) {
    setInput(entry.ticker);
    setDisplayTicker(entry.ticker);
    setDisplayName(entry.name);
    localStorage.setItem('st_ticker', entry.ticker);
    localStorage.setItem('st_name', entry.name);
    persistHistory(entry.ticker, entry.name);
    setSuggestions([]);
    setOpen(false);
    navigate(entry.ticker);
  }

  function handleSelectHistory(entry: HistoryEntry) {
    setInput(entry.ticker);
    setDisplayTicker(entry.ticker);
    setDisplayName(entry.name);
    localStorage.setItem('st_ticker', entry.ticker);
    localStorage.setItem('st_name', entry.name);
    setSuggestions([]);
    setOpen(false);
    navigate(entry.ticker);
  }

  function handleDeleteHistory(e: React.MouseEvent, ticker: string) {
    e.stopPropagation();
    if (!userId) return;
    const next = deleteHistoryItem(userId, ticker);
    setHistory(next);
    if (next.length === 0) setOpen(false);
  }

  function handleClearHistory(e: React.MouseEvent) {
    e.stopPropagation();
    if (!userId) return;
    clearAllHistory(userId);
    setHistory([]);
    setOpen(false);
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const t = input.trim();
    // 숫자 코드면 바로 이동, 문자면 첫 번째 검색 결과 사용
    if (/^\d{6}$/.test(t)) {
      localStorage.setItem('st_ticker', t);
      localStorage.removeItem('st_name'); // useEffect에서 BFF로 재조회
      const name = searchStocks(t, 1).find((s) => s.ticker === t)?.name ?? '';
      persistHistory(t, name);
      navigate(t);
    } else if (suggestions.length > 0) {
      handleSelect(activeIdx >= 0 ? suggestions[activeIdx] : suggestions[0]);
    } else {
      // suggestions 없을 때 로컬 DB 폴백 — 한글 회사명 등 ticker 무효 입력 방지
      const found = searchStocks(t, 1);
      if (found.length > 0) {
        handleSelect(found[0]);
        return;
      }
    }
    setOpen(false);
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (!open) return;
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setActiveIdx((i) => Math.min(i + 1, suggestions.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setActiveIdx((i) => Math.max(i - 1, -1));
    } else if (e.key === 'Escape') {
      setOpen(false);
    }
  }

  // blur 시 약간 지연 후 닫기 (클릭 이벤트보다 먼저 blur 발생하는 것 방지)
  function handleBlur() {
    closeTimer.current = setTimeout(() => setOpen(false), 150);
  }
  function handleFocus() {
    if (closeTimer.current) clearTimeout(closeTimer.current);
    if (suggestions.length > 0) {
      setOpen(true);
    } else if (!input.trim() && history.length > 0) {
      // 빈 입력 포커스 시 히스토리 드롭다운 표시
      setOpen(true);
    }
  }

  useEffect(() => () => { if (closeTimer.current) clearTimeout(closeTimer.current); }, []);

  return (
    <header
      style={{
        height: 48,
        backgroundColor: 'var(--color-surface)',
        borderBottom: '1px solid var(--color-border)',
        display: 'flex',
        alignItems: 'center',
        padding: '0 16px',
        gap: 24,
        flexShrink: 0,
      }}
    >
      {/* Logo */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 168 }}>
        <span style={{ color: 'var(--color-accent)', fontSize: 18, fontWeight: 700 }}>◈</span>
        <span style={{ color: 'var(--color-text)', fontWeight: 700, fontSize: 14, letterSpacing: 0.5 }}>
          Stock Trader
        </span>
      </div>

      {/* Ticker / 기업명 검색 */}
      <form onSubmit={handleSubmit} style={{ display: 'flex', gap: 6, position: 'relative' }}>
        <div style={{ position: 'relative' }}>
          <input
            value={input}
            onChange={(e) => handleChange(e.target.value)}
            onKeyDown={handleKeyDown}
            onBlur={handleBlur}
            onFocus={handleFocus}
            placeholder="종목코드 / 기업명"
            autoComplete="off"
            style={{
              width: 148,
              padding: '4px 10px',
              backgroundColor: 'var(--color-card)',
              border: '1px solid var(--color-border)',
              borderRadius: 4,
              color: 'var(--color-text)',
              fontSize: 13,
              outline: 'none',
              fontFamily: 'var(--font-mono)',
            }}
          />

          {/* 드롭다운: 빈 입력 → 히스토리, 입력 중 → 자동완성 */}
          {open && (!input.trim() ? history.length > 0 : suggestions.length > 0) && (
            <div
              style={{
                position: 'absolute',
                top: '100%',
                left: 0,
                width: 240,
                backgroundColor: 'var(--color-card)',
                border: '1px solid var(--color-border)',
                borderRadius: 4,
                marginTop: 2,
                boxShadow: '0 6px 20px rgba(0,0,0,0.4)',
                zIndex: 9998,
                overflow: 'hidden',
              }}
            >
              {/* 히스토리 모드 (입력 없을 때) */}
              {!input.trim() && history.length > 0 && (
                <>
                  <div style={{
                    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                    padding: '5px 10px', borderBottom: '1px solid var(--color-border)',
                  }}>
                    <span style={{ fontSize: 10, color: 'var(--color-muted)', fontWeight: 600, letterSpacing: 0.5 }}>
                      최근 조회
                    </span>
                    <span
                      onMouseDown={handleClearHistory}
                      style={{ fontSize: 10, color: 'var(--color-muted)', cursor: 'pointer', padding: '1px 4px' }}
                    >
                      전체 삭제
                    </span>
                  </div>
                  {history.map((h) => (
                    <div
                      key={h.ticker}
                      onMouseDown={() => handleSelectHistory(h)}
                      style={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        padding: '6px 10px',
                        fontSize: 12,
                        cursor: 'pointer',
                        borderBottom: '1px solid var(--color-border)',
                      }}
                      onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = 'rgba(88,166,255,0.07)')}
                      onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = 'transparent')}
                    >
                      <span style={{ display: 'flex', alignItems: 'center', gap: 8, flex: 1, overflow: 'hidden' }}>
                        <span style={{ fontSize: 10, color: 'var(--color-muted)' }}>🕐</span>
                        <span className="mono" style={{ color: 'var(--color-accent)', fontSize: 12, fontWeight: 600, flexShrink: 0 }}>
                          {h.ticker}
                        </span>
                        {h.name && (
                          <span style={{ color: 'var(--color-muted)', fontSize: 11, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                            {h.name}
                          </span>
                        )}
                      </span>
                      <span
                        onMouseDown={(e) => handleDeleteHistory(e, h.ticker)}
                        style={{ fontSize: 12, color: 'var(--color-muted)', cursor: 'pointer', padding: '0 4px', flexShrink: 0, lineHeight: 1 }}
                        title="삭제"
                      >
                        ×
                      </span>
                    </div>
                  ))}
                </>
              )}

              {/* 자동완성 모드 (입력 중) */}
              {input.trim() && suggestions.map((s, i) => (
                <div
                  key={s.ticker}
                  onMouseDown={() => handleSelect(s)}
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    padding: '6px 10px',
                    fontSize: 12,
                    cursor: 'pointer',
                    backgroundColor:
                      i === activeIdx ? 'rgba(88,166,255,0.12)' : 'transparent',
                    borderBottom:
                      i < suggestions.length - 1
                        ? '1px solid var(--color-border)'
                        : 'none',
                  }}
                >
                  <span style={{ color: 'var(--color-text)', fontWeight: i === activeIdx ? 600 : 400 }}>
                    {s.name}
                  </span>
                  <span style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                    <span
                      style={{
                        fontSize: 10,
                        padding: '1px 4px',
                        borderRadius: 3,
                        backgroundColor: s.market === 'KOSPI'
                          ? 'rgba(88,166,255,0.12)'
                          : 'rgba(63,185,80,0.12)',
                        color: s.market === 'KOSPI'
                          ? 'var(--color-accent)'
                          : 'var(--color-up)',
                        border: s.market === 'KOSPI'
                          ? '1px solid rgba(88,166,255,0.25)'
                          : '1px solid rgba(63,185,80,0.25)',
                      }}
                    >
                      {s.market}
                    </span>
                    <span
                      className="mono"
                      style={{ color: 'var(--color-muted)', fontSize: 11 }}
                    >
                      {s.ticker}
                    </span>
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>

        <button
          type="submit"
          style={{
            padding: '4px 10px',
            backgroundColor: 'var(--color-accent)',
            color: '#fff',
            border: 'none',
            borderRadius: 4,
            fontSize: 12,
            cursor: 'pointer',
            fontWeight: 600,
          }}
        >
          조회
        </button>
      </form>

      {/* 현재 조회 종목: 코드 + 기업명 — mounted 후에만 렌더(localStorage SSR 안전) */}
      {mounted && displayTicker && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, borderLeft: '1px solid var(--color-border)', paddingLeft: 12, flexShrink: 0 }}>
          <span style={{ fontFamily: 'var(--font-mono)', fontSize: 13, fontWeight: 700, color: 'var(--color-text)', whiteSpace: 'nowrap' }}>
            {displayTicker}
          </span>
          {displayName && (
            <span style={{ fontSize: 13, color: 'var(--color-muted)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: 120 }}>
              {displayName}
            </span>
          )}
        </div>
      )}

      {/* Index mini-ticker */}
      <div style={{ display: 'flex', gap: 20, flex: 1 }}>
        {INDICES.map((idx) => (
          <div key={idx.label} style={{ display: 'flex', gap: 6, alignItems: 'baseline' }}>
            <span style={{ color: 'var(--color-muted)', fontSize: 11 }}>{idx.label}</span>
            <span className="mono" style={{ fontSize: 13, fontWeight: 600 }}>
              {idx.value}
            </span>
            <span
              className="mono"
              style={{ fontSize: 11, color: idx.up ? 'var(--color-up)' : 'var(--color-down)' }}
            >
              {idx.change}
            </span>
          </div>
        ))}
      </div>

      {/* Right: time + theme toggle + env */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <ClockDisplay />
        <button
          onClick={toggle}
          title={theme === 'dark' ? '라이트 테마로 전환' : '다크 테마로 전환'}
          suppressHydrationWarning
          style={{
            width: 28,
            height: 28,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            backgroundColor: 'var(--color-card)',
            border: '1px solid var(--color-border)',
            borderRadius: 4,
            cursor: 'pointer',
            fontSize: 14,
            color: 'var(--color-muted)',
            transition: 'color 0.15s',
          }}
        >
          {theme === 'dark' ? '☀' : '◑'}
        </button>
        <span
          style={{
            padding: '2px 8px',
            borderRadius: 3,
            fontSize: 10,
            fontWeight: 700,
            letterSpacing: 1,
            backgroundColor: 'rgba(63,185,80,0.15)',
            color: 'var(--color-up)',
            border: '1px solid rgba(63,185,80,0.3)',
          }}
        >
          SIMULATION
        </span>
      </div>
    </header>
  );
}

function ClockDisplay() {
  const [time, setTime] = useState('');

  useEffect(() => {
    function tick() {
      setTime(
        new Date().toLocaleTimeString('ko-KR', {
          hour: '2-digit',
          minute: '2-digit',
          second: '2-digit',
        }),
      );
    }
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, []);

  return (
    <span className="mono" style={{ fontSize: 12, color: 'var(--color-muted)', minWidth: 72 }}>
      {time}
    </span>
  );
}
