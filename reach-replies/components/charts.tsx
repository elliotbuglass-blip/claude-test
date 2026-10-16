"use client";

// Hand-written inline SVG, ported from the prototype's lineChart / barChart /
// drawGrowth / hover / axis. No charting library — see docs/06-design.md.
// Built as JSX, so React escapes every label; no string-built SVG.

import { useRef, useState, type ReactNode } from "react";
import { fmt, full, niceTop, shortDate } from "@/lib/format";
import { nearCrossing, HORIZON, type Forecast } from "@/lib/growth";

interface TipPoint { x: number; y: number; text: string }

/** Hover finds the nearest x and places the tooltip as a % of the viewBox, so it tracks at any width. */
function Chart({ W, H, label, points, children }: { W: number; H: number; label: string; points: TipPoint[]; children: ReactNode }) {
  const ref = useRef<SVGSVGElement>(null);
  const [tip, setTip] = useState<TipPoint | null>(null);

  function move(clientX: number) {
    const svg = ref.current;
    if (!svg || !points.length) return;
    const box = svg.getBoundingClientRect();
    const cx = ((clientX - box.left) / box.width) * W;
    let best = points[0], bd = Infinity;
    for (const p of points) { const d = Math.abs(p.x - cx); if (d < bd) { bd = d; best = p; } }
    setTip(best);
  }

  return (
    <div className="chartwrap">
      <svg
        ref={ref} className="chart" viewBox={`0 0 ${W} ${H}`} role="img" aria-label={label}
        onMouseMove={(e) => move(e.clientX)} onMouseLeave={() => setTip(null)}
        onTouchMove={(e) => move(e.touches[0].clientX)} onTouchEnd={() => setTip(null)}
      >
        {children}
      </svg>
      <div className="tip" style={tip ? { opacity: 1, left: `${(tip.x / W) * 100}%`, top: `${(tip.y / H) * 100}%` } : undefined}>
        {tip?.text}
      </div>
    </div>
  );
}

function Axis({ padL, padT, ih, W, right = 6, top, bottom = 0, ticks }: { padL: number; padT: number; ih: number; W: number; right?: number; top: number; bottom?: number; ticks: number }) {
  const out: ReactNode[] = [];
  for (let i = 0; i <= ticks; i++) {
    const f = i / ticks, y = padT + ih - f * ih;
    out.push(
      <g key={i}>
        <line x1={padL} y1={y.toFixed(1)} x2={W - right} y2={y.toFixed(1)} stroke="var(--line)" strokeWidth="1" />
        <text x={padL - (right > 6 ? 10 : 9)} y={(y + 3.5).toFixed(1)} textAnchor="end" fill="var(--muted)" fontSize="10" fontWeight="500">{fmt(bottom + (top - bottom) * f)}</text>
      </g>,
    );
  }
  return <>{out}</>;
}

// ---- line chart -----------------------------------------------------------

export function LineChart({ rows, unit, label, H = 210 }: { rows: { date: string; value: number }[]; unit: string; label: string; H?: number }) {
  const W = 760;
  if (!rows.length) return null;
  const padL = 48, padT = 10, padB = 26, iw = W - padL - 6, ih = H - padT - padB;
  const vals = rows.map((r) => r.value || 0);
  const top = niceTop(Math.max(...vals));
  const X = (i: number) => padL + (rows.length <= 1 ? iw / 2 : (i / (rows.length - 1)) * iw);
  const Y = (v: number) => padT + ih - (v / top) * ih;
  const line = rows.map((_, i) => `${i ? "L" : "M"}${X(i).toFixed(1)} ${Y(vals[i]).toFixed(1)}`).join(" ");
  const li = rows.length - 1;

  return (
    <Chart W={W} H={H} label={label} points={rows.map((r, i) => ({ x: X(i), y: Y(vals[i]), text: `${shortDate(r.date)}  ${fmt(vals[i])} ${unit}` }))}>
      <Axis padL={padL} padT={padT} ih={ih} W={W} top={top} ticks={2} />
      <path d={`${line} L ${X(li).toFixed(1)} ${padT + ih} L ${X(0).toFixed(1)} ${padT + ih} Z`} fill="var(--ink-soft)" opacity="0.55" />
      <path d={line} fill="none" stroke="var(--fg)" strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />
      <circle cx={X(li).toFixed(1)} cy={Y(vals[li]).toFixed(1)} r="4" fill="var(--fg)" />
      <text x={padL} y={H - 5} fill="var(--muted)" fontSize="10" fontWeight="500">{shortDate(rows[0].date)}</text>
      <text x={W - 6} y={H - 5} textAnchor="end" fill="var(--muted)" fontSize="10" fontWeight="500">{shortDate(rows[li].date)}</text>
    </Chart>
  );
}

// ---- bar chart ------------------------------------------------------------

export function BarChart({ items, unit, label, labelEvery = 1, H = 210 }: { items: { label: string; value: number }[]; unit: string; label: string; labelEvery?: number; H?: number }) {
  const W = 760;
  if (!items.length) return null;
  const padL = 48, padT = 10, padB = 26, iw = W - padL - 6, ih = H - padT - padB;
  const vals = items.map((d) => d.value || 0);
  const top = niceTop(Math.max(...vals));
  const bw = Math.max(2, iw / items.length - 2);
  const X = (i: number) => padL + i * (iw / items.length);
  const Y = (v: number) => padT + ih - (v / top) * ih;

  return (
    <Chart W={W} H={H} label={label} points={items.map((d, i) => ({ x: X(i) + bw / 2, y: Y(vals[i]), text: `${d.label}  ${fmt(vals[i])} ${unit}` }))}>
      <Axis padL={padL} padT={padT} ih={ih} W={W} top={top} ticks={2} />
      {items.map((d, i) => (
        <g key={i}>
          <rect x={X(i).toFixed(1)} y={Y(vals[i]).toFixed(1)} width={bw.toFixed(1)} height={Math.max(1, padT + ih - Y(vals[i])).toFixed(1)}
            rx="1.5" fill="var(--fg)" opacity={i === items.length - 1 ? 1 : 0.72} />
          {labelEvery && i % labelEvery === 0 ? (
            <text x={(X(i) + bw / 2).toFixed(1)} y={H - 5} textAnchor="middle" fill="var(--muted)" fontSize="10" fontWeight="500">{d.label}</text>
          ) : null}
        </g>
      ))}
    </Chart>
  );
}

// ---- growth projection ----------------------------------------------------

const dm = (d: string) => new Date(d).toLocaleDateString("en-GB", { day: "numeric", month: "short" });

export function GrowthChart({ f }: { f: Forecast }) {
  const W = 760, H = 250, padL = 56, padT = 20, padB = 30;
  const iw = W - padL - 12, ih = H - padT - padB;
  const { hist, proj, base, crossings } = f;
  const dayMin = hist[0].day, dayMax = HORIZON;
  const end = proj[proj.length - 1];
  const top = niceTop(Math.max(end.hi, base));
  const bottom = Math.max(0, Math.floor((Math.min(hist[0].value, base, end.lo) * 0.95) / 1000) * 1000);
  const X = (day: number) => padL + ((day - dayMin) / (dayMax - dayMin)) * iw;
  const Y = (v: number) => padT + ih - ((v - bottom) / (top - bottom)) * ih;

  const hiPath = proj.map((p, i) => `${i ? "L" : "M"}${X(p.day).toFixed(1)} ${Y(p.hi).toFixed(1)}`).join(" ");
  const loPath = proj.slice().reverse().map((p) => `L${X(p.day).toFixed(1)} ${Y(p.lo).toFixed(1)}`).join(" ");
  const hPath = hist.map((p, i) => `${i ? "L" : "M"}${X(p.day).toFixed(1)} ${Y(p.value).toFixed(1)}`).join(" ");
  const pPath = proj.map((p, i) => `${i ? "L" : "M"}${X(p.day).toFixed(1)} ${Y(p.mid).toFixed(1)}`).join(" ");
  const tx = X(0), ty = Y(base);

  // Milestones surface in the tooltip only — drawing them on the chart collided into mush.
  const points: TipPoint[] = [
    ...hist.map((p) => ({ x: X(p.day), y: Y(p.value), text: `${dm(p.date)}   ${full(p.value)}` })),
    ...proj.slice(1).map((p) => {
      const near = nearCrossing(crossings, p.day);
      return { x: X(p.day), y: Y(p.mid), text: `${dm(p.date)}   ${fmt(p.mid)}${near ? `   ·   crosses ${fmt(near.value)}` : ""}` };
    }),
  ];

  return (
    <Chart W={W} H={H} label="Projected followers over the next six months, with a 15% band either side" points={points}>
      <Axis padL={padL} padT={padT} ih={ih} W={W} right={12} top={top} bottom={bottom} ticks={3} />
      <path d={`${hiPath} ${loPath} Z`} fill="var(--ink-soft)" opacity="0.85" />
      <path d={hPath} fill="none" stroke="var(--fg)" strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />
      <path d={pPath} fill="none" stroke="var(--fg)" strokeWidth="2" strokeDasharray="7 5" strokeLinecap="round" />
      <line x1={tx.toFixed(1)} y1={padT} x2={tx.toFixed(1)} y2={padT + ih} stroke="var(--ink-mid)" strokeWidth="1" />
      <circle cx={tx.toFixed(1)} cy={ty.toFixed(1)} r="7" fill="var(--bg)" />
      <circle cx={tx.toFixed(1)} cy={ty.toFixed(1)} r="5" fill="var(--fg)" />
      <text x={(tx + 11).toFixed(1)} y={(padT + 11).toFixed(1)} fill="var(--fg)" fontSize="10.5" fontWeight="700" letterSpacing="0.08em">YOU ARE HERE</text>
      <text x={(tx + 11).toFixed(1)} y={(padT + 24).toFixed(1)} fill="var(--muted)" fontSize="10.5" fontWeight="500">{full(base)} today</text>
      <circle cx={X(end.day).toFixed(1)} cy={Y(end.mid).toFixed(1)} r="4" fill="var(--fg)" />
      <text x={W - 12} y={(Y(end.mid) - 12).toFixed(1)} textAnchor="end" fill="var(--fg)" fontSize="12" fontWeight="700">{fmt(end.mid)}</text>
      <text x={padL} y={H - 7} fill="var(--muted)" fontSize="10" fontWeight="500">{dm(hist[0].date)}</text>
      <text x={W - 12} y={H - 7} textAnchor="end" fill="var(--muted)" fontSize="10" fontWeight="500">
        {new Date(end.date).toLocaleDateString("en-GB", { month: "short", year: "numeric" })}
      </text>
    </Chart>
  );
}

/** Shown in place of a chart when there is nothing honest to draw. */
export function ChartMessage({ H = 160, children }: { H?: number; children: string }) {
  return (
    <svg className="chart" viewBox={`0 0 760 ${H}`} role="img" aria-label={children}>
      <text x="54" y={H / 2} fill="var(--muted)" fontSize="12">{children}</text>
    </svg>
  );
}
