// Net-follower maths, backwards reconstruction and the straight-line projection.
// See docs/04-data.md. This is the one piece of real logic in the app.

export interface GrowthRow {
  date: string; // YYYY-MM-DD
  /** Insights `follower_count`: gross NEW follows that day. Not a total. */
  followerCount: number | null;
  /** Insights `follows_and_unfollows`: follows + unfollows combined. */
  followsAndUnfollows: number | null;
}

export const MILESTONES = [25_000, 30_000, 40_000, 50_000, 60_000, 75_000, 100_000, 150_000, 200_000, 250_000, 500_000, 1_000_000];
export const BAND = 0.15;
export const HORIZON = 182;
const DAY_MS = 86_400_000;

/** Rows where both readings are zero are reporting gaps, not quiet days. */
export function cleanRows(rows: GrowthRow[]): GrowthRow[] {
  return rows
    .filter((r) => r && r.date && !((r.followerCount ?? 0) === 0 && (r.followsAndUnfollows ?? 0) === 0))
    .sort((a, b) => (a.date < b.date ? -1 : a.date > b.date ? 1 : 0));
}

/** net = 2 × follows − activity. Falls back to gross when activity is absent. */
export function netFor(r: GrowthRow): number {
  const gross = r.followerCount ?? 0;
  const activity = r.followsAndUnfollows ?? 0;
  return activity ? 2 * gross - activity : gross;
}

export interface HistPoint { day: number; date: string; value: number }
export interface ProjPoint { day: number; date: string; mid: number; lo: number; hi: number }
export interface Crossing { value: number; days: number; date: string }

export interface Forecast {
  hist: HistPoint[];
  proj: ProjPoint[];
  crossings: Crossing[];
  base: number;
  rate: number;
  days: number;
  gained: number; // gross follows
  lost: number;
  net: number;
}

/**
 * Walks history backwards from today's real total, so the right-hand end is
 * anchored to truth, then projects forward at the flat average net rate.
 */
export function buildForecast(rows: GrowthRow[], base: number, today: Date = new Date()): Forecast | null {
  if (!base || !rows?.length) return null;
  const clean = cleanRows(rows);
  if (!clean.length) return null;

  const net = clean.map(netFor);
  const netTotal = net.reduce((a, b) => a + b, 0);
  const grossTotal = clean.reduce((s, r) => s + (r.followerCount ?? 0), 0);
  const rate = netTotal / net.length;

  const hist: HistPoint[] = [];
  let running = base;
  for (let i = clean.length - 1; i >= 0; i--) {
    hist.unshift({ day: i - (clean.length - 1), date: clean[i].date, value: running });
    running -= net[i];
  }
  hist[hist.length - 1].value = base;

  const proj: ProjPoint[] = [];
  for (let k = 0; k <= HORIZON; k += 7) {
    proj.push({
      day: k,
      date: new Date(today.getTime() + k * DAY_MS).toISOString(),
      mid: base + rate * k,
      lo: base + rate * (1 - BAND) * k,
      hi: base + rate * (1 + BAND) * k,
    });
  }

  const end = proj[proj.length - 1];
  const crossings: Crossing[] =
    rate > 0
      ? MILESTONES.filter((m) => m > base && m <= end.mid).map((m) => {
          const days = (m - base) / rate;
          return { value: m, days, date: new Date(today.getTime() + days * DAY_MS).toISOString() };
        })
      : [];

  return { hist, proj, crossings, base, rate, days: clean.length, gained: grossTotal, lost: grossTotal - netTotal, net: netTotal };
}

/** The milestone a projected point is within 3.5 days of, if any. */
export function nearCrossing(crossings: Crossing[], day: number): Crossing | null {
  let near: Crossing | null = null;
  for (const c of crossings) if (Math.abs(c.days - day) <= 3.5) near = c;
  return near;
}
