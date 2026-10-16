"use client";

import { useEffect, useState } from "react";
import type { Reel } from "@/lib/instagram";
import { fmt, shortDate } from "@/lib/format";
import { useApi } from "./api";

export default function Content({ active }: { active: boolean }) {
  const [seen, setSeen] = useState(active);
  useEffect(() => { if (active) setSeen(true); }, [active]);
  return seen ? <Reels /> : null;
}

function Reels() {
  const [state] = useApi<Reel[]>("/api/instagram/media");

  let note = "Loading…";
  let body: React.ReactNode = <ul className="rows"><li className="skel" /><li className="skel" /><li className="skel" /></ul>;

  if (state.status === "error") {
    note = "Couldn't load";
    body = <ul className="rows"><li className="msg">{state.error.message}</li></ul>;
  } else if (state.status === "ok" && !state.data.length) {
    note = "Nothing posted";
    body = <ul className="rows"><li className="msg">Nothing posted in the last 7 days.</li></ul>;
  } else if (state.status === "ok") {
    const rows = state.data;
    const wins = rows.filter((r) => r.views >= 50_000).length;
    const totalViews = rows.reduce((s, r) => s + r.views, 0);
    note = `${rows.length} reels · ${fmt(totalViews)} views · ${wins} over 50k`;
    body = (
      <ul className="rows">
        {rows.map((r) => {
          const rate = r.views ? (r.likes / r.views) * 100 : 0;
          return (
            <li className="row" key={r.id}>
              <div className="row-main">
                <div className="row-title">{(r.caption || "No caption").split("\n")[0]}</div>
                <div className="row-meta">
                  {shortDate(r.date)} · {fmt(r.likes)} likes · {rate.toFixed(1)}% like rate
                  {r.permalink ? <> · <a href={r.permalink} target="_blank" rel="noopener noreferrer">open</a></> : null}
                </div>
                <div style={{ marginTop: 8 }}>
                  {r.views >= 50_000 ? <span className="tag win">cleared</span> : r.views < 5_000 ? <span className="tag">flat</span> : <span className="tag">mid</span>}
                </div>
              </div>
              <div className="row-num">{fmt(r.views)}<span className="u">views</span></div>
            </li>
          );
        })}
      </ul>
    );
  }

  return (
    <>
      <div className="sec-head"><p className="eyebrow">Reels · last 7 days</p><span className="sec-note">{note}</span></div>
      {body}
    </>
  );
}
