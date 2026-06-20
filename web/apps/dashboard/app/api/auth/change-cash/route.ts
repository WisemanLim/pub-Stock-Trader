import { NextRequest, NextResponse } from 'next/server';
import { updateCash } from '@/lib/server/auth-db';
import { verifyToken } from '@/lib/server/auth-core';

const BFF_URL = process.env.BFF_URL ?? 'http://localhost:3002';

export async function POST(req: NextRequest) {
  const authHeader = req.headers.get('authorization');
  if (!authHeader?.startsWith('Bearer ')) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  const payload = await verifyToken(authHeader.slice(7));
  if (!payload) return NextResponse.json({ error: 'Invalid token' }, { status: 401 });

  const { initial_cash } = await req.json();
  if (typeof initial_cash !== 'number' || initial_cash < 0) {
    return NextResponse.json({ error: '유효한 예수금 금액을 입력하세요.' }, { status: 400 });
  }

  updateCash(payload.sub, initial_cash);

  // risk-engine paper account cash 동기화 (미기동 시 무시)
  try {
    await fetch(`${BFF_URL}/api/paper/set-cash`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ cash: initial_cash }),
      signal: AbortSignal.timeout(2000),
    });
  } catch { /* BFF/risk-engine 미기동 시 무시 */ }

  return NextResponse.json({ ok: true });
}
