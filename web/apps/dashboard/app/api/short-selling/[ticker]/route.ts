import { NextResponse } from 'next/server';

const BFF_URL = process.env.BFF_URL ?? 'http://localhost:3002';

export async function GET(
  _req: Request,
  { params }: { params: Promise<{ ticker: string }> },
) {
  const { ticker } = await params;
  if (!/^[A-Z0-9]{6}$/i.test(ticker)) {
    return NextResponse.json({ error: 'invalid ticker' }, { status: 400 });
  }

  try {
    const upstream = await fetch(
      `${BFF_URL}/api/short-selling/${ticker.toUpperCase()}`,
      { cache: 'no-store', signal: AbortSignal.timeout(3000) },
    );
    if (!upstream.ok) throw new Error(`BFF ${upstream.status}`);
    const data = await upstream.json();
    return NextResponse.json(data);
  } catch {
    return NextResponse.json({ ticker, rows: [], count: 0 });
  }
}
