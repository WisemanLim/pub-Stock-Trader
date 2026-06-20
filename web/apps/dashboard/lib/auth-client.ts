const TOKEN_KEY = 'st_token';
const USER_KEY = 'st_user';
const REMEMBER_KEY = 'st_remember_id';
const SAVED_EMAIL_KEY = 'st_saved_email';
const AUTO_LOGIN_KEY = 'st_auto_login';
const SAVED_CREDS_KEY = 'st_saved_creds';

// ── 자동로그인 자격증명 암호화 (AES-256-GCM, Web Crypto API) ────────────────
// PBKDF2로 앱 고정 솔트에서 키 도출 → 평문 노출 방지. XSS 환경에선 근본 한계 있음.
const _APP_SALT = 'stock-trader-auto-login-v1';

async function _deriveKey(): Promise<CryptoKey> {
  const enc = new TextEncoder();
  const mat = await window.crypto.subtle.importKey(
    'raw', enc.encode(_APP_SALT), 'PBKDF2', false, ['deriveKey'],
  );
  return window.crypto.subtle.deriveKey(
    { name: 'PBKDF2', salt: enc.encode('st-device-key'), iterations: 100_000, hash: 'SHA-256' },
    mat,
    { name: 'AES-GCM', length: 256 },
    false,
    ['encrypt', 'decrypt'],
  );
}

export async function saveEncryptedCreds(email: string, password: string): Promise<void> {
  try {
    const key = await _deriveKey();
    const enc = new TextEncoder();
    const iv = window.crypto.getRandomValues(new Uint8Array(12));
    const cipher = await window.crypto.subtle.encrypt(
      { name: 'AES-GCM', iv },
      key,
      enc.encode(JSON.stringify({ email, password })),
    );
    localStorage.setItem(SAVED_CREDS_KEY, JSON.stringify({
      iv: btoa(String.fromCharCode(...iv)),
      data: btoa(String.fromCharCode(...new Uint8Array(cipher))),
    }));
  } catch { /* 무시 */ }
}

export async function loadEncryptedCreds(): Promise<{ email: string; password: string } | null> {
  try {
    const raw = localStorage.getItem(SAVED_CREDS_KEY);
    if (!raw) return null;
    const { iv: ivB64, data: dataB64 } = JSON.parse(raw) as { iv: string; data: string };
    const key = await _deriveKey();
    const iv = Uint8Array.from(atob(ivB64), c => c.charCodeAt(0));
    const cipher = Uint8Array.from(atob(dataB64), c => c.charCodeAt(0));
    const plain = await window.crypto.subtle.decrypt({ name: 'AES-GCM', iv }, key, cipher);
    return JSON.parse(new TextDecoder().decode(plain)) as { email: string; password: string };
  } catch {
    return null;
  }
}

export function clearEncryptedCreds(): void {
  localStorage.removeItem(SAVED_CREDS_KEY);
}

export interface SessionUser {
  id: string;
  email: string;
  name: string;
  initial_cash: number;
}

// autologin=true → localStorage(영속). false → sessionStorage(탭 종료 시 삭제).
export function storeSession(token: string, user: SessionUser, autologin = true): void {
  const store = autologin ? localStorage : sessionStorage;
  store.setItem(TOKEN_KEY, token);
  store.setItem(USER_KEY, JSON.stringify(user));
  // 반대쪽 store 잔여 항목 정리
  if (autologin) {
    sessionStorage.removeItem(TOKEN_KEY);
    sessionStorage.removeItem(USER_KEY);
  } else {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
  }
}

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY) ?? sessionStorage.getItem(TOKEN_KEY);
}

export function getStoredUser(): SessionUser | null {
  const raw = localStorage.getItem(USER_KEY) ?? sessionStorage.getItem(USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as SessionUser;
  } catch {
    return null;
  }
}

export function clearSession(clearCreds = true): void {
  [localStorage, sessionStorage].forEach(s => {
    s.removeItem(TOKEN_KEY);
    s.removeItem(USER_KEY);
  });
  if (clearCreds) clearEncryptedCreds();
}

export function isLoggedIn(): boolean {
  return !!(localStorage.getItem(TOKEN_KEY) ?? sessionStorage.getItem(TOKEN_KEY));
}

export function updateStoredUser(patch: Partial<SessionUser>): void {
  const user = getStoredUser();
  if (!user) return;
  const store = localStorage.getItem(USER_KEY) ? localStorage : sessionStorage;
  store.setItem(USER_KEY, JSON.stringify({ ...user, ...patch }));
}

// ── 아이디 기억하기 ─────────────────────────────────────
export function saveRememberEmail(email: string): void {
  localStorage.setItem(REMEMBER_KEY, 'true');
  localStorage.setItem(SAVED_EMAIL_KEY, email);
}

export function clearRememberEmail(): void {
  localStorage.removeItem(REMEMBER_KEY);
  localStorage.removeItem(SAVED_EMAIL_KEY);
}

export function getRememberedEmail(): string | null {
  if (localStorage.getItem(REMEMBER_KEY) !== 'true') return null;
  return localStorage.getItem(SAVED_EMAIL_KEY);
}

// ── 자동로그인 설정 저장 ────────────────────────────────
export function saveAutoLoginPref(on: boolean): void {
  localStorage.setItem(AUTO_LOGIN_KEY, on ? 'true' : 'false');
}

export function getAutoLoginPref(): boolean {
  return localStorage.getItem(AUTO_LOGIN_KEY) !== 'false'; // 기본 true
}
