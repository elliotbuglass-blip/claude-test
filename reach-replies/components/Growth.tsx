"use client";

import { useEffect, useState } from "react";
import type { MonthViews, Total } from "@/lib/instagram";
import type { Snapshot } from "@/lib/db";
import { buildForecast, type GrowthRow } from "@/lib/growth";
import { fmt, monthYear } from "@/lib/format";
import { BarChart, ChartMessage, GrowthChart, LineChart } from "./charts";
import { useApi, type Load } from "./api";

/** Mounts its data on first view, so the 14-month history isn't fetched on every load. */
export default function Growth({ total, active }: { total: Load<Total>; active: boolean }) {
  const [seen, setSeen] = useState(active);
  useEffect(() => { if (active) setSeen(true); }, [active]);
  if (!seen) return null;
  return <GrowthBody total={total} />;
}

function GrowthBody({ total }: { total: Load<Total> }) {
  const [growth] = useApi<GrowthRow[]>("/api/instagram/growth");
  const [long] = useApi<MonthViews[]>("/api/instagram/long");
  const [bank] = useApi<Snapshot[]>("/api/instagram/banked");

  return (
    <>
      <Projection total={total} growth={growth} />

      <div className="chartblock" style={{ borderBottom: 0 }}>
        <div className="chart-head">
          <p className="eyebrow">Monthly views · since August 2025</p>
          <span className="chart-cap">Instagram holds no follower history beyond 30 days. This is the long view that does exist.</span>
        </div>
        {long.status === "ok" ? (
          <BarChart
            items={long.data.map((m) => ({ label: new Date(m.month + "-01T00:00:00Z").toLocaleDateString("en-GB", { month: "short", timeZone: "UTC" }), value: m.views }))}
            unit="views" label="Monthly views since August 2025"
          />
        ) : long.status === "error" ? (
          <p className="msg">{long.error.message}</p>
        ) : (
          <div className="skel" />
        )}
      </div>

      <div className="sec-head" style={{ marginTop: 38 }}>
        <p className="eyebrow">Follower history · banked here</p>
        <span className="sec-note">{bankNote(bank)}</span>
      </div>
      {bank.status === "ok" && bank.data.length >= 2 ? (
        <LineChart rows={bank.data.map((d) => ({ date: d.day, value: d.total }))} unit="followers" H={160} label="Follower totals recorded by this page" />
      ) : bank.status === "ok" ? (
        <ChartMessage>{bank.data.length ? "Recording started. Come back tomorrow for the first line." : "Nothing recorded yet. The first reading lands at 06:17 tomorrow."}</ChartMessage>
      ) : bank.status === "error" ? (
        <p className="msg">{bank.error.message}</p>
      ) : (
        <div className="skel" />
      )}
      <p className="foot" style={{ marginTop: 14 }}>
        This page records your follower total once a day. Instagram won&rsquo;t give the past, so this builds the real history from here on.
      </p>
    </>
  );
}

function bankNote(bank: Load<Snapshot[]>): string {
  if (bank.status === "loading") return "";
  if (bank.status === "error") return "Couldn't read the record";
  const d = bank.data;
  if (d.length < 2) return `${d.length} day recorded — the chart fills in from here`;
  const diff = d[d.length - 1].total - d[0].total;
  return `${d.length} days recorded · ${diff >= 0 ? "+" : ""}${fmt(diff)} since`;
}

function Projection({ total, growth }: { total: Load<Total>; growth: Load<GrowthRow[]> }) {
  const head = (note: string) => (
    <div className="sec-head">
      <p className="eyebrow">Six-month projection</p>
      <span className="sec-note">{note}</span>
    </div>
  );

  if (growth.status === "error") return <>{head("Unavailable")}<p className="msg">{growth.error.message}</p></>;
  if (total.status === "error") return <>{head("Unavailable")}<p className="msg">{total.error.message}</p></>;
  if (growth.status === "loading" || total.status === "loading") return <>{head("Calculating…")}<div className="skel" style={{ height: 250 }} /></>;

  const f = buildForecast(growth.data, total.data.followers);
  if (!f) return <>{head("Unavailable")}<p className="msg">No data came back from Instagram for that period.</p></>;

  const end = f.proj[f.proj.length - 1];
  const rate = Math.round(f.rate);
  const n = (x: number) => x.toLocaleString("en-GB");

  return (
    <>
      {head(`${fmt(end.mid)} by ${monthYear(new Date(end.date))}`)}
      <GrowthChart f={f} />
      <div className="legend">
        <span><i />Last {f.days} days</span>
        <span><i className="dash" />Projected at your current rate</span>
        <span><i className="band" />15% either side</span>
        <span>{rate >= 0 ? "+" : ""}{rate} a day, net</span>
      </div>
      <p className="foot" style={{ marginTop: 20 }}>
        Over the last {f.days} days you gained {n(f.gained)} followers and lost {n(f.lost)}, a net {n(f.net)} — about {rate} a day.
        The dashed line carries that same rate forward; the shading is 15% either side. Hover the line for the date you cross each
        round number. It assumes nothing changes, and most of this growth comes from car content, so it holds only while that access does.
      </p>
    </>
  );
}
