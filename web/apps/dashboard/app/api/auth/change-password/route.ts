import { NextRequest, NextResponse } from 'next/server';
import { findUserById, updatePassword } from '@/lib/server/auth-db';
import { verifyPassword, hashPassword, verifyToken } from '@/lib/server/auth-core';

export async function POST(req: NextRequest) {
  const authHeader = req.headers.get('authorization');
  if (!authHeader?.startsWith('Bearer ')) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  const payload = await verifyToken(authHeader.slice(7));
  if (!payload) return NextResponse.json({ error: 'Invalid token' }, { status: 401 });

  const { current_password, new_password } = await req.json();
  if (!current_password || !new_password) {
    return NextResponse.json({ error: '현재 비밀번호와 새 비밀번호를 입력하세요.' }, { status: 400 });
  }
  if (new_password.length < 8) {
    return NextResponse.json({ error: '새 비밀번호는 8자 이상이어야 합니다.' }, { status: 400 });
  }

  const user = findUserById(payload.sub);
  if (!user) return NextResponse.json({ error: 'User not found' }, { status: 404 });

  const valid = await verifyPassword(current_password, user.password_hash);
  if (!valid) {
    return NextResponse.json({ error: '현재 비밀번호가 올바르지 않습니다.' }, { status: 400 });
  }

  const newHash = await hashPassword(new_password);
  updatePassword(user.id, newHash);

  return NextResponse.json({ ok: true });
}
