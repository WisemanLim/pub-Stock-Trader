import { NextResponse } from 'next/server';

const BFF_URL = process.env.BFF_URL ?? 'http://localhost:3002';

export async function GET(req: Request) {
  const { searchParams } = new URL(req.url);
  const ticker = searchParams.get('ticker') ?? '';
  const params = new URLSearchParams();
  if (ticker) params.set('ticker', ticker);

  try {
    const upstream = await fetch(
      `${BFF_URL}/api/market-alerts${params.size ? `?${params}` : ''}`,
      { cache: 'no-store', signal: AbortSignal.timeout(3000) },
    );
    if (!upstream.ok) throw new Error(`BFF ${upstream.status}`);
    const data = await upstream.json();
    return NextResponse.json(data);
  } catch {
    return NextResponse.json({ alerts: [], count: 0, caution: 0, warning: 0, danger: 0 });
  }
}
