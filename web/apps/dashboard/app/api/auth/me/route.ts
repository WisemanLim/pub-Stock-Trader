import { NextRequest, NextResponse } from 'next/server';
import { findUserById } from '@/lib/server/auth-db';
import { verifyToken } from '@/lib/server/auth-core';

export async function GET(req: NextRequest) {
  const authHeader = req.headers.get('authorization');
  if (!authHeader?.startsWith('Bearer ')) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  const payload = await verifyToken(authHeader.slice(7));
  if (!payload) {
    return NextResponse.json({ error: 'Invalid token' }, { status: 401 });
  }

  const user = findUserById(payload.sub);
  if (!user) {
    return NextResponse.json({ error: 'User not found' }, { status: 404 });
  }

  return NextResponse.json({
    id: user.id,
    email: user.email,
    name: user.name,
    initial_cash: user.initial_cash,
    totp_enabled: !!user.totp_enabled,
    created_at: user.created_at,
  });
}
