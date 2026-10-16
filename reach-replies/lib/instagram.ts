// Instagram Graph API client, plus long-lived token refresh. Works with either
// of Meta's two setups:
//   - "Instagram API with Instagram Login" → graph.instagram.com (tokens start "IG")
//   - "Instagram API with Facebook Login"  → graph.facebook.com (needs a linked Page)
// The setup is picked from the token itself; IG_LOGIN=instagram|facebook overrides.
//
// METRIC NAMES: see docs/04-data.md. Everything Meta-specific lives in the
// constants immediately below so a rename is a one-line change. Run
// GET /api/health after deploying — it calls each read once and reports which
// ones Meta accepted.

import { AppError } from "./errors";
import { cached, getToken, hasDb, saveToken } from "./db";
import { iso } from "./format";
import type { GrowthRow } from "./growth";

const VERSION = process.env.IG_GRAPH_VERSION || "v23.0";

type Login = "instagram" | "facebook";

function loginFor(token: string): Login {
  const forced = process.env.IG_LOGIN;
  if (forced === "instagram" || forced === "facebook") return forced;
  return token.startsWith("IG") ? "instagram" : "facebook";
}

function base(login: Login): string {
  return login === "instagram" ? `https://graph.instagram.com/${VERSION}` : `https://graph.facebook.com/${VERSION}`;
}

export const METRICS = {
  views: "views",               // total plays; replaced `impressions`
  reach: "reach",               // unique accounts
  newFollows: "follower_count", // gross new follows per day, 30-day cap
  followActivity: "follows_and_unfollows",
  mediaViews: "views",
} as const;

export const LONG_FROM = "2025-08-25";

const DAY = 86_400;
const MIN15 = 15 * 60;
/** Insights for a day can still move for ~48h; after that a day is settled. */
const SETTLED_AFTER_DAYS = 3;

// ---- token ----------------------------------------------------------------

async function accessToken(): Promise<string> {
  const row = await getToken("instagram").catch(() => null);
  const token = row?.access || process.env.IG_ACCESS_TOKEN;
  if (!token) throw new AppError("ig_not_configured");
  return token;
}

/** With Instagram Login the token already names the account, so "me" works without IG_USER_ID. */
function userId(): string {
  const id = process.env.IG_USER_ID;
  if (id) return id;
  if (process.env.IG_ACCESS_TOKEN && loginFor(process.env.IG_ACCESS_TOKEN) === "instagram") return "me";
  throw new AppError("ig_not_configured");
}

interface GraphError { error?: { code?: number; error_subcode?: number; message?: string; type?: string } }

async function graph<T>(path: string, params: Record<string, string | number | undefined> = {}, token?: string): Promise<T> {
  // token === "" means the call authenticates with its own params (token exchange).
  const auth = token ?? (await accessToken());
  const login = loginFor(auth || process.env.IG_ACCESS_TOKEN || "");
  const url = new URL(path.startsWith("http") ? path : base(login) + path);
  for (const [k, v] of Object.entries(params)) if (v !== undefined) url.searchParams.set(k, String(v));
  if (auth) url.searchParams.set("access_token", auth);

  let res: Response;
  try {
    res = await fetch(url, { cache: "no-store" });
  } catch (e) {
    throw new AppError("unknown", e);
  }
  const body = (await res.json().catch(() => ({}))) as T & GraphError;
  if (!res.ok || body.error) {
    const code = body.error?.code;
    if (code === 190 || code === 102) throw new AppError("ig_token_expired", body.error);
    if (code === 4 || code === 17 || code === 32 || code === 613 || res.status === 429) throw new AppError("ig_rate_limited", body.error);
    throw new AppError("unknown", { status: res.status, path, error: body.error });
  }
  return body;
}

/** Runs tasks with a small concurrency limit, keeping order. */
async function pool<I, O>(items: I[], limit: number, fn: (item: I) => Promise<O>): Promise<O[]> {
  const out: O[] = new Array(items.length);
  let next = 0;
  await Promise.all(
    Array.from({ length: Math.min(limit, items.length) }, async () => {
      while (next < items.length) {
        const i = next++;
        out[i] = await fn(items[i]);
      }
    }),
  );
  return out;
}

// ---- days -----------------------------------------------------------------

function utcDayStart(d: string): number {
  return Math.floor(Date.parse(d + "T00:00:00Z") / 1000);
}

/** The last `n` complete days, oldest first. Today is excluded — it is partial. */
export function lastDays(n: number, now = new Date()): string[] {
  const out: string[] = [];
  const today = Date.parse(iso(now) + "T00:00:00Z");
  for (let i = n; i >= 1; i--) out.push(iso(new Date(today - i * DAY * 1000)));
  return out;
}

function ttlForDay(day: string): number {
  const age = (Date.now() - Date.parse(day + "T00:00:00Z")) / (DAY * 1000);
  return age > SETTLED_AFTER_DAYS ? 400 * DAY : MIN15;
}

interface TotalValueResponse {
  data: { name: string; total_value?: { value?: number; breakdowns?: { results?: { dimension_values: string[]; value: number }[] }[] } }[];
}

/** One metric's total for one day (metric_type=total_value). Settled days cache for good. */
async function dayTotal(metric: string, day: string, breakdown?: string): Promise<number | null> {
  return cached(`ig:day:${metric}:${breakdown ?? "-"}:${day}`, ttlForDay(day), async () => {
    const since = utcDayStart(day);
    const res = await graph<TotalValueResponse>(`/${userId()}/insights`, {
      metric, period: "day", metric_type: "total_value", since, until: since + DAY, breakdown,
    });
    const tv = res.data?.[0]?.total_value;
    if (!tv) return null;
    if (typeof tv.value === "number") return tv.value;
    const results = tv.breakdowns?.[0]?.results;
    return results ? results.reduce((s, r) => s + (r.value || 0), 0) : null;
  });
}

interface TimeSeriesResponse { data: { name: string; values: { value: number; end_time: string }[] }[] }

/** A metric as a daily time series over a window (≤30 days). Keyed by date. */
async function daySeries(metric: string, from: string, to: string): Promise<Record<string, number>> {
  const res = await graph<TimeSeriesResponse>(`/${userId()}/insights`, {
    metric, period: "day", since: utcDayStart(from), until: utcDayStart(to) + DAY,
  });
  const out: Record<string, number> = {};
  for (const v of res.data?.[0]?.values ?? []) {
    // end_time marks the end of the day the value covers.
    const d = iso(new Date(Date.parse(v.end_time) - DAY * 1000));
    out[d] = v.value;
  }
  return out;
}

// ---- the five reads -------------------------------------------------------

export interface OverviewRow { date: string; views: number | null; reach: number | null; followerCount: number | null }
export interface OverviewData {
  rows: OverviewRow[];
  /** Unique accounts over the whole 30-day window — not the sum of daily reach, which double-counts. */
  reach30: number | null;
}

export async function overview(): Promise<OverviewData> {
  return cached("ig:overview", MIN15, async () => {
    const days = lastDays(30);
    const since = utcDayStart(days[0]);
    const [views, reach, follows, window] = await Promise.all([
      pool(days, 6, (d) => dayTotal(METRICS.views, d)),
      pool(days, 6, (d) => dayTotal(METRICS.reach, d)),
      daySeries(METRICS.newFollows, days[0], days[days.length - 1]),
      graph<TotalValueResponse>(`/${userId()}/insights`, {
        metric: METRICS.reach, period: "day", metric_type: "total_value", since, until: utcDayStart(days[days.length - 1]) + DAY,
      }),
    ]);
    const rows = days.map((date, i) => ({ date, views: views[i], reach: reach[i], followerCount: follows[date] ?? null }));
    if (rows.every((r) => r.views == null && r.reach == null && r.followerCount == null)) throw new AppError("ig_empty");
    return { rows, reach30: window.data?.[0]?.total_value?.value ?? null };
  });
}

export interface Total { followers: number; media: number; readAt: string }

/** Profile fields are current at the moment of the call. Short cache so polling stays honest. */
export async function total(): Promise<Total> {
  return cached("ig:total", 240, async () => {
    const r = await graph<{ followers_count?: number; media_count?: number }>(`/${userId()}`, { fields: "followers_count,media_count" });
    if (typeof r.followers_count !== "number") throw new AppError("ig_empty");
    return { followers: r.followers_count, media: r.media_count ?? 0, readAt: new Date().toISOString() };
  });
}

export async function growth(): Promise<GrowthRow[]> {
  return cached("ig:growth", MIN15, async () => {
    const days = lastDays(30);
    const [follows, activity] = await Promise.all([
      daySeries(METRICS.newFollows, days[0], days[days.length - 1]),
      pool(days, 6, (d) => dayTotal(METRICS.followActivity, d, "follow_type")),
    ]);
    return days.map((date, i) => ({ date, followerCount: follows[date] ?? null, followsAndUnfollows: activity[i] }));
  });
}

export interface MonthViews { month: string; views: number }

/** Monthly views since LONG_FROM. Completed months cache for good; only this month refetches. */
export async function longView(now = new Date()): Promise<MonthViews[]> {
  const months: string[] = [];
  const start = new Date(LONG_FROM + "T00:00:00Z");
  for (let d = new Date(Date.UTC(start.getUTCFullYear(), start.getUTCMonth(), 1)); d <= now; d.setUTCMonth(d.getUTCMonth() + 1)) {
    months.push(iso(d).slice(0, 7));
  }
  const thisMonth = iso(now).slice(0, 7);
  const yesterday = iso(new Date(Date.parse(iso(now) + "T00:00:00Z") - DAY * 1000));

  return pool(months, 3, (m) =>
    cached(`ig:month:${m}`, m === thisMonth ? 6 * 3600 : 3650 * DAY, async () => {
      const first = m === LONG_FROM.slice(0, 7) ? LONG_FROM : `${m}-01`;
      const [y, mo] = m.split("-").map(Number);
      const lastOfMonth = iso(new Date(Date.UTC(y, mo, 0)));
      const last = m === thisMonth ? yesterday : lastOfMonth;
      if (last < first) return { month: m, views: 0 };
      // Insights windows are capped at 30 days, so split each month in two.
      const mid = `${m}-15`;
      const windows: [string, string][] = first > mid ? [[first, last]] : last <= mid ? [[first, last]] : [[first, mid], [`${m}-16`, last]];
      let views = 0;
      for (const [a, b] of windows) {
        const since = utcDayStart(a);
        const res = await graph<TotalValueResponse>(`/${userId()}/insights`, {
          metric: METRICS.views, period: "day", metric_type: "total_value", since, until: utcDayStart(b) + DAY,
        });
        views += res.data?.[0]?.total_value?.value ?? 0;
      }
      return { month: m, views };
    }),
  );
}

export interface Reel { id: string; date: string; views: number; likes: number; caption: string; permalink: string }

interface MediaResponse {
  data: { id: string; caption?: string; media_product_type?: string; permalink?: string; timestamp: string; like_count?: number }[];
  paging?: { next?: string };
}

export async function reels(): Promise<Reel[]> {
  return cached("ig:reels", MIN15, async () => {
    const cutoff = Date.now() - 7 * DAY * 1000;
    const recent: MediaResponse["data"] = [];
    let page = await graph<MediaResponse>(`/${userId()}/media`, {
      fields: "id,caption,media_product_type,permalink,timestamp,like_count", limit: 50,
    });
    for (let guard = 0; guard < 5; guard++) {
      let older = false;
      for (const m of page.data ?? []) {
        if (Date.parse(m.timestamp) < cutoff) { older = true; break; }
        if (m.media_product_type === "REELS") recent.push(m);
      }
      if (older || !page.paging?.next) break;
      page = await graph<MediaResponse>(page.paging.next);
    }
    const views = await pool(recent, 6, async (m) => {
      const r = await graph<{ data: { values?: { value: number }[]; total_value?: { value: number } }[] }>(`/${m.id}/insights`, { metric: METRICS.mediaViews });
      const d = r.data?.[0];
      return d?.total_value?.value ?? d?.values?.[0]?.value ?? 0;
    });
    return recent
      .map((m, i) => ({
        id: m.id, date: m.timestamp, views: views[i], likes: m.like_count ?? 0,
        caption: m.caption ?? "", permalink: m.permalink ?? "",
      }))
      .sort((a, b) => b.views - a.views)
      .slice(0, 40);
  });
}

// ---- token refresh (called from the daily cron) ---------------------------

export interface RefreshResult { refreshed: boolean; expiresAt: string | null }

async function tokenExpiry(token: string): Promise<Date | null> {
  const appId = process.env.IG_APP_ID, secret = process.env.IG_APP_SECRET;
  if (!appId || !secret) return null;
  const r = await graph<{ data?: { expires_at?: number; data_access_expires_at?: number } }>(
    "/debug_token", { input_token: token }, `${appId}|${secret}`,
  );
  const at = r.data?.expires_at;
  return at ? new Date(at * 1000) : null;
}

/** If the long-lived token is within 10 days of expiry, exchange it and store the new one. */
export async function refreshTokenIfDue(): Promise<RefreshResult> {
  const row = await getToken("instagram").catch(() => null);
  const token = row?.access || process.env.IG_ACCESS_TOKEN;
  if (!token) throw new AppError("ig_not_configured");
  const login = loginFor(token);
  const appId = process.env.IG_APP_ID, secret = process.env.IG_APP_SECRET;
  if (login === "facebook" && (!appId || !secret)) throw new AppError("ig_not_configured");

  let expiresAt = row?.expiresAt ?? null;
  if (!expiresAt && login === "facebook") {
    expiresAt = await tokenExpiry(token);
    if (hasDb()) await saveToken("instagram", token, expiresAt);
  }
  // Unknown expiry (a freshly seeded Instagram Login token) counts as due: refreshing early is harmless.
  const due = !expiresAt || expiresAt.getTime() - Date.now() < 10 * DAY * 1000;
  if (!due) return { refreshed: false, expiresAt: expiresAt?.toISOString() ?? null };

  const r = login === "instagram"
    ? await graph<{ access_token: string; expires_in?: number }>(
        "https://graph.instagram.com/refresh_access_token", { grant_type: "ig_refresh_token" }, token)
    : await graph<{ access_token: string; expires_in?: number }>(
        "/oauth/access_token",
        { grant_type: "fb_exchange_token", client_id: appId, client_secret: secret, fb_exchange_token: token },
        "",
      );
  const next = r.expires_in ? new Date(Date.now() + r.expires_in * 1000) : login === "facebook" ? await tokenExpiry(r.access_token) : null;
  if (hasDb()) await saveToken("instagram", r.access_token, next);
  console.log(`[instagram] token refreshed, new expiry ${next?.toISOString() ?? "unknown"}`);
  return { refreshed: true, expiresAt: next?.toISOString() ?? null };
}
