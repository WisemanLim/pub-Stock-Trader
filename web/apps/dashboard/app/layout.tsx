import type { ReactNode } from 'react';
import './globals.css';
import ClientLayout from '@/components/ClientLayout';
import { ThemeProvider } from '@/components/ThemeProvider';

export const metadata = {
  title: 'Stock Trader — 대시보드',
  description: 'F6.2 실시간 포트폴리오·시그널 대시보드',
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="ko" suppressHydrationWarning>
      <body
        style={{
          margin: 0,
          display: 'flex',
          flexDirection: 'column',
          height: '100vh',
          backgroundColor: 'var(--color-bg)',
          color: 'var(--color-text)',
          overflow: 'hidden',
        }}
      >
        <ThemeProvider>
          <ClientLayout>
            {children}
          </ClientLayout>
        </ThemeProvider>
      </body>
    </html>
  );
}
