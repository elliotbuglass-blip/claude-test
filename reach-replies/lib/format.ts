// Number and date formatting, carried over from the prototype. en-GB throughout.

/** A thread is owed a follow-up after this many working days. */
export const QUIET_DAYS = 5;

export function fmt(n: number | null | undefined): string {
  if (n == null || Number.isNaN(n)) return "—";
  n = Math.round(n);
  const a = Math.abs(n);
  if (a >= 1_000_000) return (n / 1_000_000).toFixed(a >= 10_000_000 ? 1 : 2).replace(/\.?0+$/, "") + "M";
  if (a >= 10_000) return Math.round(n / 1000) + "k";
  return n.toLocaleString("en-GB");
}

/** A full figure with thousands separators, for numbers quoted exactly (hero, tooltips). */
export function full(n: number | null | undefined): string {
  if (n == null || Number.isNaN(n)) return "—";
  return Math.round(n).toLocaleString("en-GB");
}

export function iso(d: Date): string {
  return d.toISOString().slice(0, 10);
}

export function shortDate(d: string | Date): string {
  const t = new Date(d);
  return Number.isNaN(t.getTime()) ? String(d) : t.toLocaleDateString("en-GB", { day: "numeric", month: "short" });
}

export function monthYear(d: Date): string {
  return d.toLocaleDateString("en-GB", { month: "long", year: "numeric" });
}

/** Counts forward from `from`, excluding Saturdays and Sundays. A Friday email on Monday is 1. */
export function workingDaysBetween(from: Date, to: Date): number {
  const d = new Date(from.getTime());
  let n = 0;
  while (d < to) {
    d.setDate(d.getDate() + 1);
    const w = d.getDay();
    if (w !== 0 && w !== 6) n++;
  }
  return n;
}

export function median(a: number[]): number {
  if (!a.length) return 0;
  const s = a.slice().sort((x, y) => x - y);
  const m = Math.floor(s.length / 2);
  return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
}

export function when(d: string | Date, now = Date.now()): string {
  const t = new Date(d);
  if (Number.isNaN(t.getTime())) return "";
  const h = (now - t.getTime()) / 3_600_000;
  if (h < 1) return Math.max(1, Math.round(h * 60)) + " min ago";
  if (h < 24) return Math.round(h) + (Math.round(h) === 1 ? " hour ago" : " hours ago");
  return t.toLocaleDateString("en-GB", { day: "numeric", month: "short" });
}

/** Rounds an axis maximum up to a sensible value. */
export function niceTop(max: number): number {
  if (max <= 0) return 1;
  const step = Math.pow(10, Math.floor(Math.log10(max)));
  let t = Math.ceil(max / step) * step;
  if (t / max > 1.9) t = Math.ceil(max / (step / 2)) * (step / 2);
  return t;
}
