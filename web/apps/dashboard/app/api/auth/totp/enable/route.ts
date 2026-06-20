import { NextRequest, NextResponse } from 'next/server';
import { findUserById, enableTotp } from '@/lib/server/auth-db';
import { verifyToken, verifyTotpCode } from '@/lib/server/auth-core';

export async function POST(req: NextRequest) {
  const authHeader = req.headers.get('authorization');
  if (!authHeader?.startsWith('Bearer ')) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  const payload = await verifyToken(authHeader.slice(7));
  if (!payload) return NextResponse.json({ error: 'Invalid token' }, { status: 401 });

  const { code } = await req.json();
  if (!code) {
    return NextResponse.json({ error: 'TOTP 코드를 입력하세요.' }, { status: 400 });
  }

  const user = findUserById(payload.sub);
  if (!user) return NextResponse.json({ error: 'User not found' }, { status: 404 });

  if (!user.totp_secret) {
    return NextResponse.json({ error: 'TOTP 설정을 먼저 생성하세요.' }, { status: 400 });
  }

  if (!verifyTotpCode(code, user.totp_secret)) {
    return NextResponse.json({ error: 'TOTP 코드가 올바르지 않습니다.' }, { status: 400 });
  }

  enableTotp(user.id);
  return NextResponse.json({ ok: true });
}
