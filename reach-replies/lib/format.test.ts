import { describe, expect, it } from "vitest";
import { fmt, median, niceTop, workingDaysBetween } from "./format";

describe("fmt", () => {
  it("formats per the design spec", () => {
    expect(fmt(10_240_000)).toBe("10.2M");
    expect(fmt(4_290_000)).toBe("4.29M");
    expect(fmt(4_000_000)).toBe("4M");
    expect(fmt(30_121)).toBe("30k");
    expect(fmt(9_999)).toBe("9,999");
    expect(fmt(null)).toBe("—");
    expect(fmt(NaN)).toBe("—");
  });
});

describe("workingDaysBetween", () => {
  it("does not count a weekend", () => {
    // Friday 9 Oct 2026 → Monday 12 Oct 2026
    expect(workingDaysBetween(new Date(2026, 9, 9, 10), new Date(2026, 9, 12, 10))).toBe(1);
  });
  it("counts a full working week", () => {
    expect(workingDaysBetween(new Date(2026, 9, 5, 10), new Date(2026, 9, 12, 10))).toBe(5);
  });
});

describe("median", () => {
  it("handles odd and even lengths", () => {
    expect(median([5, 1, 3])).toBe(3);
    expect(median([1, 2, 3, 100])).toBe(2.5);
    expect(median([])).toBe(0);
  });
});

describe("niceTop", () => {
  it("rounds up to a sensible axis maximum", () => {
    expect(niceTop(0)).toBe(1);
    expect(niceTop(870)).toBe(900);
    expect(niceTop(1_100)).toBe(2_000);
  });
});
