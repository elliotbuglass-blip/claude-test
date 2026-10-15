// Gmail over IMAP with an app password. See docs/03-auth-and-setup.md for why
// this is not OAuth. Read-only: this app never writes to the mailbox.
//
// Threads: Gmail's IMAP exposes X-GM-THRID (imapflow's `threadId`), the same
// thread id the web UI uses, so threads are grouped by that rather than
// reconstructed from References headers.

import { ImapFlow, type FetchMessageObject, type ListResponse } from "imapflow";
import { simpleParser } from "mailparser";
import { AppError } from "./errors";
import { QUIET_DAYS, workingDaysBetween } from "./format";

function email(): string {
  const e = process.env.GOOGLE_EMAIL;
  if (!e || !process.env.GOOGLE_APP_PASSWORD) throw new AppError("gmail_auth", "GOOGLE_EMAIL / GOOGLE_APP_PASSWORD not set");
  return e.toLowerCase();
}

async function withImap<T>(fn: (c: ImapFlow, boxes: { all: string }) => Promise<T>): Promise<T> {
  const user = email();
  const client = new ImapFlow({
    host: "imap.gmail.com", port: 993, secure: true,
    auth: { user, pass: (process.env.GOOGLE_APP_PASSWORD || "").replace(/\s+/g, "") },
    logger: false, emitLogs: false,
  });
  client.on("error", (e) => console.error("[gmail] socket error", e));
  try {
    await client.connect();
  } catch (e) {
    const err = e as { authenticationFailed?: boolean; code?: string };
    if (err?.authenticationFailed) throw new AppError("gmail_auth", e);
    throw new AppError("gmail_unreachable", e);
  }
  try {
    // UK accounts may use "[Google Mail]/…" — find folders by special-use flag, not name.
    const list: ListResponse[] = await client.list();
    const by = (flag: string, fallback: string) => list.find((b) => b.specialUse === flag)?.path ?? fallback;
    return await fn(client, { all: by("\\All", "[Gmail]/All Mail") });
  } catch (e) {
    if (e instanceof AppError) throw e;
    throw new AppError("gmail_unreachable", e);
  } finally {
    await client.logout().catch(() => client.close());
  }
}

export function gmailUrl(threadId: string): string {
  let hex = threadId;
  try { hex = BigInt(threadId).toString(16); } catch { /* already hex */ }
  return `https://mail.google.com/mail/u/?authuser=${encodeURIComponent(process.env.GOOGLE_EMAIL ?? "")}#all/${hex}`;
}

function name(a?: { name?: string; address?: string }): string {
  return (a?.name || a?.address || "them").replace(/^"|"$/g, "").trim();
}

function isDraft(m: FetchMessageObject): boolean {
  return !!(m.flags?.has("\\Draft") || m.labels?.has("\\Draft"));
}

function isMine(m: FetchMessageObject): boolean {
  if (m.labels?.has("\\Sent")) return true;
  return (m.envelope?.from?.[0]?.address || "").toLowerCase() === email();
}

function sentAt(m: FetchMessageObject): Date {
  return new Date(m.envelope?.date ?? m.internalDate ?? 0);
}

function snippetOf(text: string): string {
  return text.replace(/\s+/g, " ").trim().slice(0, 220);
}

// ---- inbox ----------------------------------------------------------------

export interface InboxThread { threadId: string; subject: string; from: string; date: string; snippet: string; url: string }

export async function inbox(): Promise<InboxThread[]> {
  return withImap(async (c) => {
    const lock = await c.getMailboxLock("INBOX", { readOnly: true });
    try {
      const uids = await c.search(
        { gmraw: "newer_than:1d -category:promotions -category:social -category:updates -in:draft" },
        { uid: true },
      );
      if (!uids || !uids.length) return [];
      const msgs = await c.fetchAll(uids.slice(-40), { uid: true, envelope: true, threadId: true, internalDate: true, source: true }, { uid: true });

      const latest = new Map<string, FetchMessageObject>();
      for (const m of msgs) {
        const key = m.threadId ?? String(m.uid);
        const prev = latest.get(key);
        if (!prev || sentAt(m) > sentAt(prev)) latest.set(key, m);
      }
      const threads = [...latest.values()].sort((a, b) => +sentAt(b) - +sentAt(a)).slice(0, 25);
      return Promise.all(threads.map(async (m) => {
        const parsed = m.source ? await simpleParser(m.source).catch(() => null) : null;
        return {
          threadId: m.threadId ?? "",
          subject: m.envelope?.subject || "(no subject)",
          from: name(m.envelope?.from?.[0]),
          date: sentAt(m).toISOString(),
          snippet: snippetOf(parsed?.text ?? ""),
          url: m.threadId ? gmailUrl(m.threadId) : "",
        };
      }));
    } finally {
      lock.release();
    }
  });
}

// ---- follow-ups -----------------------------------------------------------

export interface FollowUp {
  threadId: string; subject: string; theirName: string;
  sentAt: string; workingDays: number; url: string;
}

export async function followUps(now = new Date()): Promise<FollowUp[]> {
  return withImap(async (c, boxes) => {
    const lock = await c.getMailboxLock(boxes.all, { readOnly: true });
    try {
      const sentUids = await c.search({ gmraw: "in:sent newer_than:120d older_than:4d -category:promotions" }, { uid: true });
      if (!sentUids || !sentUids.length) return [];
      const sent = await c.fetchAll(sentUids, { uid: true, threadId: true, internalDate: true }, { uid: true });

      // Most recent 50 threads Elliot wrote in, as the prototype did.
      const lastTouch = new Map<string, number>();
      for (const m of sent) if (m.threadId) lastTouch.set(m.threadId, Math.max(lastTouch.get(m.threadId) ?? 0, +new Date(m.internalDate ?? 0)));
      const threadIds = [...lastTouch.entries()].sort((a, b) => b[1] - a[1]).slice(0, 50).map(([id]) => id);

      const due: FollowUp[] = [];
      for (const threadId of threadIds) {
        const uids = await c.search({ threadId }, { uid: true });
        if (!uids || !uids.length) continue;
        const msgs = (await c.fetchAll(uids, { uid: true, envelope: true, labels: true, flags: true, internalDate: true }, { uid: true }))
          .filter((m) => !isDraft(m))
          .sort((a, b) => +sentAt(a) - +sentAt(b));
        const last = msgs[msgs.length - 1];
        if (!last || !isMine(last)) continue;
        const when = sentAt(last);
        if (Number.isNaN(when.getTime())) continue;
        const wd = workingDaysBetween(when, now);
        if (wd < QUIET_DAYS) continue;
        const them = [...msgs].reverse().find((m) => !isMine(m));
        due.push({
          threadId,
          subject: last.envelope?.subject || "(no subject)",
          theirName: them ? name(them.envelope?.from?.[0]) : name(last.envelope?.to?.[0]),
          sentAt: when.toISOString(),
          workingDays: wd,
          url: gmailUrl(threadId),
        });
      }
      return due.sort((a, b) => b.workingDays - a.workingDays);
    } finally {
      lock.release();
    }
  });
}

/** Login + mailbox list, for /api/health. */
export async function check(): Promise<{ all: string }> {
  return withImap(async (_c, boxes) => boxes);
}
