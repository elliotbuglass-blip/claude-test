import { describe, expect, it } from "vitest";
import { buildForecast, cleanRows, nearCrossing, netFor, type GrowthRow } from "./growth";

const row = (date: string, followerCount: number | null, followsAndUnfollows: number | null): GrowthRow => ({
  date, followerCount, followsAndUnfollows,
});

describe("netFor", () => {
  it("is 2 × follows − activity", () => {
    // 100 follows, 20 unfollows → activity 120 → net 80
    expect(netFor(row("2026-10-01", 100, 120))).toBe(80);
  });
  it("falls back to gross when activity is absent", () => {
    expect(netFor(row("2026-10-01", 100, 0))).toBe(100);
    expect(netFor(row("2026-10-01", 100, null))).toBe(100);
  });
  it("can go negative on a bad day", () => {
    expect(netFor(row("2026-10-01", 10, 50))).toBe(-30);
  });
});

describe("cleanRows", () => {
  it("drops rows where both readings are zero and sorts by date", () => {
    const out = cleanRows([row("2026-10-03", 5, 6), row("2026-10-01", 0, 0), row("2026-10-02", 3, 3)]);
    expect(out.map((r) => r.date)).toEqual(["2026-10-02", "2026-10-03"]);
  });
  it("keeps a row with follows but no activity", () => {
    expect(cleanRows([row("2026-10-01", 4, 0)])).toHaveLength(1);
  });
});

describe("buildForecast", () => {
  const today = new Date("2026-10-14T12:00:00Z");
  const rows = [
    row("2026-10-11", 100, 120), // net 80
    row("2026-10-12", 0, 0),     // gap — filtered
    row("2026-10-13", 200, 220), // net 180
    row("2026-10-14", 50, 60),   // net 40
  ];

  it("anchors the last history point to today's real total", () => {
    const f = buildForecast(rows, 30_000, today)!;
    expect(f.hist[f.hist.length - 1].value).toBe(30_000);
  });

  it("walks backwards subtracting net movement", () => {
    const f = buildForecast(rows, 30_000, today)!;
    expect(f.hist.map((p) => p.value)).toEqual([30_000 - 40 - 180, 30_000 - 40, 30_000]);
    expect(f.hist.map((p) => p.day)).toEqual([-2, -1, 0]);
  });

  it("uses the flat average net rate over clean days only", () => {
    const f = buildForecast(rows, 30_000, today)!;
    expect(f.days).toBe(3);
    expect(f.net).toBe(300);
    expect(f.rate).toBe(100);
    expect(f.gained).toBe(350);
    expect(f.lost).toBe(50);
  });

  it("projects 182 days weekly with a ±15% band", () => {
    const f = buildForecast(rows, 30_000, today)!;
    expect(f.proj[0]).toMatchObject({ day: 0, mid: 30_000, lo: 30_000, hi: 30_000 });
    const end = f.proj[f.proj.length - 1];
    expect(end.day).toBe(182);
    expect(end.mid).toBe(30_000 + 100 * 182);
    expect(end.lo).toBeCloseTo(30_000 + 85 * 182);
    expect(end.hi).toBeCloseTo(30_000 + 115 * 182);
  });

  it("finds milestone crossings within the horizon", () => {
    const f = buildForecast(rows, 30_000, today)!;
    expect(f.crossings.map((c) => c.value)).toEqual([40_000]);
    expect(f.crossings[0].days).toBe(100);
    expect(nearCrossing(f.crossings, 98)?.value).toBe(40_000);
    expect(nearCrossing(f.crossings, 105)).toBeNull();
  });

  it("returns null with no total or no usable rows", () => {
    expect(buildForecast(rows, 0, today)).toBeNull();
    expect(buildForecast([row("2026-10-01", 0, 0)], 30_000, today)).toBeNull();
  });

  it("does not report crossings when the rate is not positive", () => {
    const f = buildForecast([row("2026-10-14", 10, 40)], 30_000, today)!;
    expect(f.rate).toBe(-20);
    expect(f.crossings).toEqual([]);
  });
});
