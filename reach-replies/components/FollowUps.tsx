"use client";

import type { FollowUp } from "@/lib/gmail";
import { QUIET_DAYS } from "@/lib/format";
import type { Load } from "./api";

export default function FollowUps({ state }: { state: Load<FollowUp[]> }) {
  let note = "Loading…";
  let body: React.ReactNode = <ul className="rows"><li className="skel" /><li className="skel" /></ul>;

  if (state.status === "error") {
    note = "Couldn't load";
    body = <ul className="rows"><li className="msg">{state.error.message}</li></ul>;
  } else if (state.status === "ok" && !state.data.length) {
    note = "Up to date";
    body = <ul className="rows"><li className="msg"><strong>Nothing owed.</strong> No thread has gone past {QUIET_DAYS} working days without a reply.</li></ul>;
  } else if (state.status === "ok") {
    note = `${state.data.length} waiting`;
    body = (
      <ul className="rows">
        {state.data.map((d) => (
          <li className="row" key={d.threadId}>
            <div className="row-main">
              <div className="row-title">{d.subject}</div>
              <div className="row-meta">
                {d.theirName} · you wrote {new Date(d.sentAt).toLocaleDateString("en-GB", { day: "numeric", month: "short" })}
              </div>
              {d.url ? <div style={{ marginTop: 9 }}><a href={d.url} target="_blank" rel="noopener noreferrer">Open in Gmail</a></div> : null}
            </div>
            <div className="row-num" style={{ color: "var(--alert)" }}>{d.workingDays}<span className="u">working days</span></div>
          </li>
        ))}
      </ul>
    );
  }

  return (
    <>
      <div className="sec-head"><p className="eyebrow">Gone quiet · {QUIET_DAYS}+ working days</p><span className="sec-note">{note}</span></div>
      {body}
    </>
  );
}
