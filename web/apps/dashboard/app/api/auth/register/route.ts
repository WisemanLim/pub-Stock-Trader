import { NextRequest, NextResponse } from 'next/server';
import { findUserByEmail, createUser, setTotpSecret } from '@/lib/server/auth-db';
import {
  hashPassword,
  signToken,
  generateTotpSecret,
  getTotpUri,
  generateQrDataUrl,
} from '@/lib/server/auth-core';

const BFF_URL = process.env.BFF_URL ?? 'http://localhost:3002';

export async function POST(req: NextRequest) {
  const { email, name, password, initial_cash } = await req.json();

  if (!email || !name || !password) {
    return NextResponse.json({ error: '필수 항목을 입력하세요.' }, { status: 400 });
  }
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    return NextResponse.json({ error: '올바른 이메일 형식을 입력하세요.' }, { status: 400 });
  }
  if (password.length < 8) {
    return NextResponse.json({ error: '비밀번호는 8자 이상이어야 합니다.' }, { status: 400 });
  }

  if (findUserByEmail(email)) {
    return NextResponse.json({ error: '이미 사용중인 이메일입니다.' }, { status: 409 });
  }

  const passwordHash = await hashPassword(password);
  const cash = typeof initial_cash === 'number' && initial_cash > 0 ? initial_cash : 100_000_000;
  const user = createUser(email, name, passwordHash, cash);

  // risk-engine paper account cash 초기화
  try {
    await fetch(`${BFF_URL}/api/paper/set-cash`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ cash: user.initial_cash }),
      signal: AbortSignal.timeout(2000),
    });
  } catch { /* BFF/risk-engine 미기동 시 무시 */ }

  const totpSecret = generateTotpSecret();
  setTotpSecret(user.id, totpSecret);

  const uri = getTotpUri(email, totpSecret);
  const qr = await generateQrDataUrl(uri);

  const token = await signToken({ sub: user.id, email: user.email, name: user.name });

  return NextResponse.json({
    token,
    user: { id: user.id, email: user.email, name: user.name, initial_cash: user.initial_cash },
    totp: { secret: totpSecret, qr },
  });
}
