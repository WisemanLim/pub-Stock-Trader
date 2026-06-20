import { NextRequest, NextResponse } from 'next/server';
import { findUserById } from '@/lib/server/auth-db';
import { verifyToken } from '@/lib/server/auth-core';

const BFF_URL = process.env.BFF_URL ?? 'http://localhost:3002';

export async function POST(req: NextRequest) {
  const authHeader = req.headers.get('authorization');
  if (!authHeader?.startsWith('Bearer ')) return NextResponse.json({ ok: false });

  const payload = await verifyToken(authHeader.slice(7));
  if (!payload) return NextResponse.json({ ok: false });

  const user = findUserById(payload.sub);
  if (!user) return NextResponse.json({ ok: false });

  try {
    await fetch(`${BFF_URL}/api/paper/set-cash`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ cash: user.initial_cash }),
      signal: AbortSignal.timeout(2000),
    });
  } catch { /* risk-engine 미기동 시 무시 */ }

  return NextResponse.json({ ok: true, initial_cash: user.initial_cash });
}
