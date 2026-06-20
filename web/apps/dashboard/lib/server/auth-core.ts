import bcrypt from 'bcryptjs';
import { SignJWT, jwtVerify } from 'jose';
import { authenticator } from 'otplib';
import QRCode from 'qrcode';

const JWT_SECRET = new TextEncoder().encode(
  process.env.AUTH_JWT_SECRET || 'stock-trader-dev-secret-change-in-prod-32chars',
);

export async function hashPassword(password: string): Promise<string> {
  return bcrypt.hash(password, 12);
}

export async function verifyPassword(password: string, hash: string): Promise<boolean> {
  return bcrypt.compare(password, hash);
}

export interface TokenPayload {
  sub: string;
  email: string;
  name: string;
}

export async function signToken(payload: TokenPayload): Promise<string> {
  return new SignJWT(payload as unknown as Record<string, unknown>)
    .setProtectedHeader({ alg: 'HS256' })
    .setIssuedAt()
    .setExpirationTime('7d')
    .sign(JWT_SECRET);
}

export async function verifyToken(token: string): Promise<TokenPayload | null> {
  try {
    const { payload } = await jwtVerify(token, JWT_SECRET);
    return payload as unknown as TokenPayload;
  } catch {
    return null;
  }
}

export function generateTotpSecret(): string {
  return authenticator.generateSecret();
}

export function verifyTotpCode(code: string, secret: string): boolean {
  try {
    return authenticator.check(code, secret);
  } catch {
    return false;
  }
}

export function getTotpUri(email: string, secret: string): string {
  return authenticator.keyuri(email, 'Stock Trader', secret);
}

export async function generateQrDataUrl(uri: string): Promise<string> {
  return QRCode.toDataURL(uri);
}
