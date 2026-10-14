"use client";

import type { InboxThread } from "@/lib/gmail";
import { when } from "@/lib/format";
import type { Load } from "./api";

export default function Inbox({ state }: { state: Load<InboxThread[]> }) {
  let note = "Loading…";
  let body: React.ReactNode = <ul className="rows"><li className="skel" /><li className="skel" /></ul>;

  if (state.status === "error") {
    note = "Couldn't load";
    body = <ul className="rows"><li className="msg">{state.error.message}</li></ul>;
  } else if (state.status === "ok" && !state.data.length) {
    note = "All clear";
    body = <ul className="rows"><li className="msg"><strong>Nothing new.</strong> No brand or outreach mail in the last 24 hours.</li></ul>;
  } else if (state.status === "ok") {
    note = `${state.data.length} new`;
    body = (
      <ul className="rows">
        {state.data.map((t) => (
          <li className="row" key={t.threadId || t.date}>
            <div className="row-main">
              <div className="row-title">{t.subject}</div>
              <div className="row-meta">{t.from} · {when(t.date)}</div>
              {t.snippet ? <div className="row-snip">{t.snippet}</div> : null}
              {t.url ? <div style={{ marginTop: 9 }}><a href={t.url} target="_blank" rel="noopener noreferrer">Open in Gmail</a></div> : null}
            </div>
          </li>
        ))}
      </ul>
    );
  }

  return (
    <>
      <div className="sec-head"><p className="eyebrow">Inbox · last 24 hours</p><span className="sec-note">{note}</span></div>
      {body}
    </>
  );
}
