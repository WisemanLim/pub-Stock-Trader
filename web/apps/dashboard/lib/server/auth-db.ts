import { DatabaseSync } from 'node:sqlite';
import { mkdirSync } from 'fs';
import path from 'path';
import { randomUUID } from 'crypto';

const DB_PATH = path.join(process.cwd(), 'data', 'auth.db');

// globalThis pattern: survives Next.js HMR module re-evaluation
type GlobalWithDb = typeof globalThis & { __authDb?: DatabaseSync };

function getDb(): DatabaseSync {
  const g = globalThis as GlobalWithDb;
  if (!g.__authDb) {
    mkdirSync(path.dirname(DB_PATH), { recursive: true });
    g.__authDb = new DatabaseSync(DB_PATH);
    g.__authDb.exec(`
      CREATE TABLE IF NOT EXISTS users (
        id            TEXT PRIMARY KEY,
        email         TEXT NOT NULL UNIQUE,
        name          TEXT NOT NULL,
        password_hash TEXT NOT NULL,
        initial_cash  REAL NOT NULL DEFAULT 100000000,
        totp_secret   TEXT,
        totp_enabled  INTEGER NOT NULL DEFAULT 0,
        created_at    TEXT NOT NULL DEFAULT (datetime('now')),
        last_login_at TEXT
      );
    `);
  }
  return g.__authDb;
}

export interface UserRow {
  id: string;
  email: string;
  name: string;
  password_hash: string;
  initial_cash: number;
  totp_secret: string | null;
  totp_enabled: number;
  created_at: string;
  last_login_at: string | null;
}

export function findUserByEmail(email: string): UserRow | undefined {
  return getDb().prepare('SELECT * FROM users WHERE email = ?').get(email) as UserRow | undefined;
}

export function findUserById(id: string): UserRow | undefined {
  return getDb().prepare('SELECT * FROM users WHERE id = ?').get(id) as UserRow | undefined;
}

export function createUser(
  email: string,
  name: string,
  passwordHash: string,
  initialCash: number,
): UserRow {
  const id = randomUUID();
  getDb()
    .prepare('INSERT INTO users (id, email, name, password_hash, initial_cash) VALUES (?, ?, ?, ?, ?)')
    .run(id, email, name, passwordHash, initialCash);
  return findUserById(id)!;
}

export function updatePassword(id: string, passwordHash: string) {
  getDb().prepare('UPDATE users SET password_hash = ? WHERE id = ?').run(passwordHash, id);
}

export function updateCash(id: string, initialCash: number) {
  getDb().prepare('UPDATE users SET initial_cash = ? WHERE id = ?').run(initialCash, id);
}

export function updateLastLogin(id: string) {
  getDb().prepare("UPDATE users SET last_login_at = datetime('now') WHERE id = ?").run(id);
}

export function setTotpSecret(id: string, secret: string) {
  getDb().prepare('UPDATE users SET totp_secret = ? WHERE id = ?').run(secret, id);
}

export function enableTotp(id: string) {
  getDb().prepare('UPDATE users SET totp_enabled = 1 WHERE id = ?').run(id);
}
