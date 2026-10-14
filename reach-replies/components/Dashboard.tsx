"use client";

import { useEffect, useState } from "react";
import type { Total, OverviewData } from "@/lib/instagram";
import type { FollowUp, InboxThread } from "@/lib/gmail";
import { useApi } from "./api";
import Overview from "./Overview";
import Growth from "./Growth";
import Content from "./Content";
import Inbox from "./Inbox";
import FollowUps from "./FollowUps";

const TABS = ["overview", "growth", "content", "inbox", "followups"] as const;
type Tab = (typeof TABS)[number];
const LABEL: Record<Tab, string> = { overview: "Overview", growth: "Growth", content: "Content", inbox: "Inbox", followups: "Follow-ups" };

export default function Dashboard() {
  const [tab, setTab] = useState<Tab>("overview");
  // The follower total is current at the moment it's read. Poll it, and step
  // to each new reading — never animate through numbers that were never true.
  const [total] = useApi<Total>("/api/instagram/total", 5 * 60_000);
  const [overview] = useApi<OverviewData>("/api/instagram/overview");
  const [inbox] = useApi<InboxThread[]>("/api/gmail/inbox", 2 * 60_000);
  const [follow] = useApi<FollowUp[]>("/api/gmail/followups");

  useEffect(() => {
    try {
      const saved = localStorage.getItem("rr-tab") as Tab | null;
      if (saved && TABS.includes(saved)) setTab(saved);
    } catch { /* storage blocked: default tab */ }
  }, []);

  function select(t: Tab) {
    setTab(t);
    try { localStorage.setItem("rr-tab", t); } catch { /* ignore */ }
  }

  function onKey(e: React.KeyboardEvent, i: number) {
    const d = e.key === "ArrowRight" ? 1 : e.key === "ArrowLeft" ? -1 : 0;
    if (!d) return;
    const next = TABS[(i + d + TABS.length) % TABS.length];
    select(next);
    document.getElementById(`tab-${next}`)?.focus();
  }

  const updated = overview.status === "ok"
    ? "Updated " + new Date().toLocaleString("en-GB", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" })
    : "";

  const inboxBadge = inbox.status === "ok" ? (inbox.data.length || "") : inbox.status === "error" ? "!" : "";
  const followBadge = follow.status === "ok" ? (follow.data.length || "") : follow.status === "error" ? "!" : "";
  const followAlert = follow.status === "ok" && follow.data.length > 0;

  return (
    <>
      <header>
        <div className="head-in">
          <div className="brandrow">
            <h1>Reach &amp; Replies</h1>
            <span className="handle">@elliotcameron._</span>
            <span className="updated">{updated}</span>
          </div>
          <nav role="tablist" aria-label="Sections">
            {TABS.map((t, i) => (
              <button
                key={t} role="tab" id={`tab-${t}`} aria-selected={tab === t} aria-controls={`p-${t}`}
                tabIndex={tab === t ? 0 : -1} onClick={() => select(t)} onKeyDown={(e) => onKey(e, i)}
              >
                {LABEL[t]}
                {t === "inbox" && <span className="badge">{inboxBadge}</span>}
                {t === "followups" && <span className={"badge" + (followAlert ? " alert" : "")}>{followBadge}</span>}
              </button>
            ))}
          </nav>
        </div>
      </header>

      <div className="wrap">
        <section id="p-overview" role="tabpanel" aria-labelledby="tab-overview" hidden={tab !== "overview"}>
          <Overview total={total} rows={overview} />
        </section>
        <section id="p-growth" role="tabpanel" aria-labelledby="tab-growth" hidden={tab !== "growth"}>
          <Growth total={total} active={tab === "growth"} />
        </section>
        <section id="p-content" role="tabpanel" aria-labelledby="tab-content" hidden={tab !== "content"}>
          <Content active={tab === "content"} />
        </section>
        <section id="p-inbox" role="tabpanel" aria-labelledby="tab-inbox" hidden={tab !== "inbox"}>
          <Inbox state={inbox} />
        </section>
        <section id="p-followups" role="tabpanel" aria-labelledby="tab-followups" hidden={tab !== "followups"}>
          <FollowUps state={follow} />
        </section>

        <div className="foot">
          Instagram figures read from Instagram directly. Email read from Gmail. Nothing is sent from this page.{" "}
          <form method="post" action="/api/logout" style={{ display: "inline" }}>
            <button className="signout" type="submit">Sign out</button>
          </form>
        </div>
      </div>
    </>
  );
}
