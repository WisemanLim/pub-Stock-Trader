import { NextRequest, NextResponse } from 'next/server';

const BFF_URL = process.env.BFF_URL ?? 'http://localhost:3002';

export async function GET(
  _req: NextRequest,
  { params }: { params: Promise<{ ticker: string }> },
) {
  const { ticker } = await params;
  try {
    const res = await fetch(`${BFF_URL}/api/stocks/${ticker}`, {
      cache: 'no-store',
      signal: AbortSignal.timeout(3000),
    });
    if (!res.ok) return NextResponse.json({ found: false, ticker, name: null, market: null });
    return NextResponse.json(await res.json());
  } catch {
    return NextResponse.json({ found: false, ticker, name: null, market: null });
  }
}
