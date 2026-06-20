import { NextRequest, NextResponse } from 'next/server';

const BFF_URL = process.env.BFF_URL ?? 'http://localhost:3002';

export async function GET(req: NextRequest) {
  const { searchParams } = new URL(req.url);
  const q = searchParams.get('q') ?? '';
  const market = searchParams.get('market') ?? 'all';
  const limit = searchParams.get('limit') ?? '10';

  try {
    const url = `${BFF_URL}/api/stocks/search?q=${encodeURIComponent(q)}&market=${market}&limit=${limit}`;
    const res = await fetch(url, { cache: 'no-store', signal: AbortSignal.timeout(3000) });
    if (!res.ok) return NextResponse.json({ results: [], count: 0 });
    return NextResponse.json(await res.json());
  } catch {
    return NextResponse.json({ results: [], count: 0 });
  }
}
