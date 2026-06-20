'use client';

import { useEffect, useState } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import { getToken } from '@/lib/auth-client';
import { Suspense } from 'react';
import Sidebar from './Sidebar';
import TopBar from './TopBar';

const PUBLIC_ROUTES = ['/login', '/register'];

export default function ClientLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [checked, setChecked] = useState(false);

  useEffect(() => {
    if (PUBLIC_ROUTES.includes(pathname)) {
      setChecked(true);
      return;
    }
    const token = getToken();
    if (!token) {
      router.replace('/login');
    } else {
      setChecked(true);
      // rebuild/재시작 후 risk-engine cash 리셋 복구 — 세션당 1회만 실행
      if (!sessionStorage.getItem('st_cash_synced')) {
        sessionStorage.setItem('st_cash_synced', '1');
        fetch('/api/auth/sync', {
          method: 'POST',
          headers: { Authorization: `Bearer ${token}` },
        }).catch(() => {});
      }
    }
  }, [pathname, router]);

  if (PUBLIC_ROUTES.includes(pathname)) {
    return <>{children}</>;
  }

  if (!checked) {
    return (
      <div style={{
        height: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        backgroundColor: 'var(--color-bg)',
        color: 'var(--color-muted)',
        fontSize: 13,
      }}>
        인증 확인 중...
      </div>
    );
  }

  return (
    <>
      <Suspense>
        <TopBar />
      </Suspense>
      <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
        <Suspense>
          <Sidebar />
        </Suspense>
        <main
          style={{
            flex: 1,
            overflow: 'auto',
            padding: 20,
            backgroundColor: 'var(--color-bg)',
          }}
        >
          {children}
        </main>
      </div>
    </>
  );
}
