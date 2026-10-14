"use client";

import { useRef, useState } from "react";
import type { FollowUp, ThreadMessage } from "@/lib/gmail";
import { QUIET_DAYS } from "@/lib/format";
import { api, post, type ApiError, type Load } from "./api";

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
    body = <ul className="rows">{state.data.map((d) => <Row key={d.threadId} d={d} />)}</ul>;
  }

  return (
    <>
      <div className="sec-head"><p className="eyebrow">Gone quiet · {QUIET_DAYS}+ working days</p><span className="sec-note">{note}</span></div>
      {body}
    </>
  );
}

type Phase = "idle" | "reading" | "drafting" | "ready" | "failed";

function Row({ d }: { d: FollowUp }) {
  const [phase, setPhase] = useState<Phase>("idle");
  const [text, setText] = useState("");
  const [msg, setMsg] = useState("");

  async function draft() {
    setMsg("");
    try {
      setPhase("reading");
      const t = await api<{ messages: ThreadMessage[] }>(`/api/gmail/thread/${encodeURIComponent(d.threadId)}`);
      setPhase("drafting");
      const transcript = t.messages.slice(-6).map((m) =>
        `--- ${m.mine ? "Elliot" : m.from} (${new Date(m.date).toUTCString()}) ---\n${m.text.slice(0, 1800)}`,
      ).join("\n\n");
      const out = await post<{ text: string }>("/api/draft", { transcript, workingDays: d.workingDays });
      setText(out.text);
      setPhase("ready");
    } catch (e) {
      setMsg((e as ApiError).message ?? "Couldn't write a draft just now. Try again.");
      setPhase("failed");
    }
  }

  const label = { idle: "Draft a follow-up", reading: "Reading thread", drafting: "Drafting", ready: "Redraft", failed: "Try again" }[phase];
  const busy = phase === "reading" || phase === "drafting";

  return (
    <li className="row">
      <div className="row-main">
        <div className="row-title">{d.subject}</div>
        <div className="row-meta">
          {d.theirName} · you wrote {new Date(d.sentAt).toLocaleDateString("en-GB", { day: "numeric", month: "short" })}
        </div>
        <div style={{ marginTop: 11, display: "flex", gap: 14, alignItems: "center", flexWrap: "wrap" }}>
          <button className="act" disabled={busy} onClick={draft}>{label}</button>
          {d.url ? <a href={d.url} target="_blank" rel="noopener noreferrer">Open in Gmail</a> : null}
        </div>
        {phase !== "idle" && (
          <div className="draft">
            {phase === "reading" && <div className="draft-note">Reading the thread…</div>}
            {phase === "drafting" && <div className="draft-note">Writing a draft…</div>}
            {phase === "failed" && <div className="draft-note">{msg}</div>}
            {phase === "ready" && <DraftEditor threadId={d.threadId} text={text} setText={setText} />}
          </div>
        )}
      </div>
      <div className="row-num" style={{ color: "var(--alert)" }}>{d.workingDays}<span className="u">working days</span></div>
    </li>
  );
}

function DraftEditor({ threadId, text, setText }: { threadId: string; text: string; setText: (s: string) => void }) {
  const [save, setSave] = useState<"idle" | "saving" | "saved">("idle");
  const [note, setNote] = useState<React.ReactNode>("Edit before sending. Nothing is sent from here.");
  const [copied, setCopied] = useState(false);

  async function saveDraft() {
    setSave("saving");
    try {
      const r = await post<{ url: string }>("/api/gmail/draft", { threadId, body: text });
      setSave("saved");
      setNote(<>Waiting in Gmail as a draft · <a href={r.url} target="_blank" rel="noopener noreferrer">open it</a>.</>);
    } catch (e) {
      setSave("idle");
      setNote((e as ApiError).message);
    }
  }

  async function copy(ta: HTMLTextAreaElement | null) {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 1600);
    } catch {
      ta?.focus(); ta?.select();
    }
  }

  const ref = useRef<HTMLTextAreaElement>(null);
  return (
    <>
      <textarea ref={ref} spellCheck value={text} onChange={(e) => { setText(e.target.value); if (save === "saved") setSave("idle"); }} aria-label="Draft follow-up" />
      <div className="draft-bar">
        <button className="act primary" disabled={save !== "idle" || !text.trim()} onClick={saveDraft}>
          {save === "saving" ? "Saving" : save === "saved" ? "Saved" : "Save to Gmail"}
        </button>
        <button className="act" onClick={() => copy(ref.current)}>{copied ? "Copied" : "Copy"}</button>
        <span className="draft-note">{note}</span>
      </div>
    </>
  );
}
