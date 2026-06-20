import { NextRequest, NextResponse } from 'next/server';
import { findUserByEmail, updateLastLogin } from '@/lib/server/auth-db';
import { verifyPassword, verifyTotpCode, signToken } from '@/lib/server/auth-core';

export async function POST(req: NextRequest) {
  const { email, password, totp_code } = await req.json();

  if (!email || !password) {
    return NextResponse.json({ error: '이메일과 비밀번호를 입력하세요.' }, { status: 400 });
  }

  const user = findUserByEmail(email);
  if (!user) {
    return NextResponse.json({ error: '이메일 또는 비밀번호가 올바르지 않습니다.' }, { status: 401 });
  }

  const valid = await verifyPassword(password, user.password_hash);
  if (!valid) {
    return NextResponse.json({ error: '이메일 또는 비밀번호가 올바르지 않습니다.' }, { status: 401 });
  }

  if (user.totp_enabled) {
    if (!totp_code) {
      return NextResponse.json({ error: 'TOTP 코드를 입력하세요.', totp_required: true }, { status: 401 });
    }
    if (!verifyTotpCode(totp_code, user.totp_secret!)) {
      return NextResponse.json({ error: 'TOTP 코드가 올바르지 않습니다.' }, { status: 401 });
    }
  }

  updateLastLogin(user.id);

  // 로그인 시 risk-engine cash sync — 회원가입 시 미기동으로 실패했을 경우 복구
  const BFF_URL = process.env.BFF_URL ?? 'http://localhost:3002';
  try {
    await fetch(`${BFF_URL}/api/paper/set-cash`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ cash: user.initial_cash }),
      signal: AbortSignal.timeout(2000),
    });
  } catch { /* BFF/risk-engine 미기동 시 무시 */ }

  const token = await signToken({ sub: user.id, email: user.email, name: user.name });

  return NextResponse.json({
    token,
    user: { id: user.id, email: user.email, name: user.name, initial_cash: user.initial_cash },
  });
}
