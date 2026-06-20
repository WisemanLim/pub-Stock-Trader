import { NextRequest, NextResponse } from 'next/server';
import { findUserById, setTotpSecret } from '@/lib/server/auth-db';
import {
  verifyToken,
  generateTotpSecret,
  getTotpUri,
  generateQrDataUrl,
} from '@/lib/server/auth-core';

export async function GET(req: NextRequest) {
  const authHeader = req.headers.get('authorization');
  if (!authHeader?.startsWith('Bearer ')) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  const payload = await verifyToken(authHeader.slice(7));
  if (!payload) return NextResponse.json({ error: 'Invalid token' }, { status: 401 });

  const user = findUserById(payload.sub);
  if (!user) return NextResponse.json({ error: 'User not found' }, { status: 404 });

  const secret = generateTotpSecret();
  setTotpSecret(user.id, secret);

  const uri = getTotpUri(user.email, secret);
  const qr = await generateQrDataUrl(uri);

  return NextResponse.json({ secret, qr });
}
