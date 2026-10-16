// Postgres via DATABASE_URL (Vercel's Neon integration, or any Postgres).
// Three tables, per docs/02-architecture.md. Without DATABASE_URL the cache
// falls back to process memory so local dev works; snapshots then can't persist.

import postgres from "postgres";

type Sql = ReturnType<typeof postgres>;

let sql: Sql | null = null;
let ready: Promise<void> | null = null;

export function hasDb(): boolean {
  return !!process.env.DATABASE_URL;
}

async function db(): Promise<Sql> {
  if (!process.env.DATABASE_URL) throw new Error("DATABASE_URL not set");
  if (!sql) {
    sql = postgres(process.env.DATABASE_URL, { max: 3, idle_timeout: 20, prepare: false });
  }
  if (!ready) {
    const s = sql;
    ready = (async () => {
      await s`create table if not exists tokens (
        provider text primary key, access text not null, refresh text,
        expires_at timestamptz, updated_at timestamptz not null default now())`;
      await s`create table if not exists follower_snapshots (day date primary key, total integer not null)`;
      await s`create table if not exists cache (key text primary key, payload jsonb not null, expires_at timestamptz not null)`;
    })().catch((e) => {
      ready = null;
      throw e;
    });
  }
  await ready;
  return sql;
}

// ---- cache ----------------------------------------------------------------

const mem = new Map<string, { payload: unknown; expires: number }>();

export async function cacheGet<T>(key: string): Promise<T | null> {
  if (!hasDb()) {
    const hit = mem.get(key);
    return hit && hit.expires > Date.now() ? (hit.payload as T) : null;
  }
  try {
    const s = await db();
    const rows = await s`select payload from cache where key = ${key} and expires_at > now()`;
    return rows.length ? (rows[0].payload as T) : null;
  } catch (e) {
    console.error("[cache] read failed", e);
    return null;
  }
}

export async function cacheSet(key: string, payload: unknown, ttlSeconds: number): Promise<void> {
  const expires = new Date(Date.now() + ttlSeconds * 1000);
  if (!hasDb()) {
    mem.set(key, { payload, expires: expires.getTime() });
    return;
  }
  try {
    const s = await db();
    await s`insert into cache (key, payload, expires_at) values (${key}, ${s.json(payload as never)}, ${expires})
            on conflict (key) do update set payload = excluded.payload, expires_at = excluded.expires_at`;
  } catch (e) {
    console.error("[cache] write failed", e);
  }
}

/** Read-through cache. */
export async function cached<T>(key: string, ttlSeconds: number, load: () => Promise<T>): Promise<T> {
  const hit = await cacheGet<T>(key);
  if (hit !== null) return hit;
  const value = await load();
  await cacheSet(key, value, ttlSeconds);
  return value;
}

// ---- tokens ---------------------------------------------------------------

export interface TokenRow { access: string; expiresAt: Date | null }

export async function getToken(provider: "instagram"): Promise<TokenRow | null> {
  if (!hasDb()) return null;
  const s = await db();
  const rows = await s`select access, expires_at from tokens where provider = ${provider}`;
  return rows.length ? { access: rows[0].access, expiresAt: rows[0].expires_at } : null;
}

export async function saveToken(provider: "instagram", access: string, expiresAt: Date | null): Promise<void> {
  const s = await db();
  await s`insert into tokens (provider, access, expires_at, updated_at) values (${provider}, ${access}, ${expiresAt}, now())
          on conflict (provider) do update set access = excluded.access, expires_at = excluded.expires_at, updated_at = now()`;
}

// ---- follower snapshots ---------------------------------------------------

export interface Snapshot { day: string; total: number }

/** Idempotent: a retry or manual run overwrites the same day. */
export async function upsertSnapshot(day: string, total: number): Promise<void> {
  const s = await db();
  await s`insert into follower_snapshots (day, total) values (${day}, ${total})
          on conflict (day) do update set total = excluded.total`;
}

export async function listSnapshots(): Promise<Snapshot[]> {
  const s = await db();
  const rows = await s`select to_char(day, 'YYYY-MM-DD') as day, total from follower_snapshots order by day`;
  return rows.map((r) => ({ day: r.day as string, total: Number(r.total) }));
}
