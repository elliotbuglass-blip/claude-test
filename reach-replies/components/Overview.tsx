"use client";

import type { OverviewData, Total } from "@/lib/instagram";
import { fmt, full, median, shortDate } from "@/lib/format";
import { BarChart, LineChart } from "./charts";
import type { Load } from "./api";

export default function Overview({ total, rows }: { total: Load<Total>; rows: Load<OverviewData> }) {
  const lede =
    total.status === "ok"
      ? `Across ${total.data.media.toLocaleString("en-GB")} posts. Instagram keeps only 30 days of follower history, so the long view is built from here on.`
      : total.status === "error"
        ? total.error.message
        : "Reading Instagram…";

  return (
    <>
      <div className="hero">
        <div>
          <p className="eyebrow">Followers</p>
          <div className="big">{total.status === "ok" ? full(total.data.followers) : "—"}</div>
        </div>
        <p className="lede">{lede}</p>
      </div>
      <Body rows={rows} />
    </>
  );
}

function Body({ rows }: { rows: Load<OverviewData> }) {
  if (rows.status === "loading") {
    return (
      <div className="tiles">
        {["Views · 30 days", "Views · 7 days", "Reach · 30 days", "New followers · 30d"].map((t) => (
          <div className="tile" key={t}><p className="eyebrow">{t}</p><div className="v">—</div><div className="sub">loading</div></div>
        ))}
      </div>
    );
  }
  if (rows.status === "error") {
    return <div className="tiles"><div className="msg" style={{ gridColumn: "1/-1" }}>{rows.error.message}</div></div>;
  }

  const r = rows.data.rows;
  // Sum only readings that came back; a missing day is not a zero.
  const sum = (xs: (number | null)[]) => xs.reduce<number>((s, v) => s + (v ?? 0), 0);
  const views = r.map((x) => x.views);
  const v30 = sum(views);
  const v7 = sum(views.slice(-7));
  const vPrev7 = sum(views.slice(-14, -7));
  const r30 = rows.data.reach30;
  const f30 = sum(r.map((x) => x.followerCount));
  const viewDays = views.filter((v) => v != null).length;
  const followDays = r.filter((x) => x.followerCount != null).length;
  const pc = vPrev7 > 0 ? Math.round(((v7 - vPrev7) / vPrev7) * 100) : null;

  const viewRows = r.filter((x) => x.views != null).map((x) => ({ date: x.date, value: x.views as number }));
  const best = viewRows.reduce<{ date: string; value: number } | null>((a, b) => (!a || b.value > a.value ? b : a), null);
  const gains = r.filter((x) => x.followerCount != null).map((x) => ({ label: shortDate(x.date), value: x.followerCount as number }));

  return (
    <>
      <div className="tiles">
        <div className="tile"><p className="eyebrow">Views · 30 days</p><div className="v">{fmt(v30)}</div><div className="sub">across {viewDays} days</div></div>
        <div className="tile">
          <p className="eyebrow">Views · 7 days</p><div className="v">{fmt(v7)}</div>
          {pc == null
            ? <div className="sub">last 7 days</div>
            : <div className={"sub " + (pc >= 0 ? "up" : "down")}>{(pc >= 0 ? "+" : "") + pc}% on previous 7</div>}
        </div>
        <div className="tile">
          <p className="eyebrow">Reach · 30 days</p><div className="v">{fmt(r30)}</div>
          <div className="sub">unique accounts</div>
        </div>
        <div className="tile">
          <p className="eyebrow">New followers · 30d</p><div className="v">+{fmt(f30)}</div>
          <div className="sub">{followDays ? Math.round(f30 / followDays) : 0} a day on average</div>
        </div>
      </div>

      <div className="chartblock">
        <div className="chart-head">
          <p className="eyebrow">Daily views · last 30 days</p>
          <span className="chart-cap">{best ? `Best day ${shortDate(best.date)} · ${fmt(best.value)} views` : ""}</span>
        </div>
        <LineChart rows={viewRows} unit="views" label="Daily views over the last 30 days" />
      </div>

      <div className="chartblock">
        <div className="chart-head">
          <p className="eyebrow">New followers per day · last 30 days</p>
          <span className="chart-cap">Median {fmt(median(gains.map((g) => g.value)))} a day</span>
        </div>
        <BarChart items={gains} unit="followers" labelEvery={7} H={170} label="New followers per day over the last 30 days" />
      </div>
    </>
  );
}
