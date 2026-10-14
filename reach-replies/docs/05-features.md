# Features

Five tabs. Selected tab persists in `localStorage` under `rr-tab` — this is the
only thing browser storage is used for. Everything else lives server-side.

Tabs use `role="tablist"` / `role="tab"` / `role="tabpanel"` with
`aria-selected` and `aria-controls`. Panels are shown and hidden with the
`hidden` attribute, not CSS.

Two tabs carry a count badge: Inbox (neutral) and Follow-ups (red when > 0).

---

## 1. Overview

**Hero** — total followers as an oversized numeral, with a line of context:
post count, and a note that Instagram keeps only 30 days of follower history.

**Four tiles** in a hairline grid:

| Tile | Sub-line |
|---|---|
| Views · 30 days | across *n* days |
| Views · 7 days | % change on previous 7 days, up or down |
| Reach · 30 days | unique accounts |
| New followers · 30d | average per day |

The 7-day tile is the only place colour appears outside the alert state: up is
foreground weight, down is the alert red.

**Daily views, last 30 days** — line chart with filled area, dot on the latest
point. Caption names the best day and its figure.

**New followers per day, last 30 days** — bar chart, latest bar at full
opacity and the rest at 0.72. Caption gives the median, not the mean — the
distribution is heavily skewed by occasional spikes and the mean misleads.

---

## 2. Growth

**Six-month projection.** Solid line for the real last 30 days (reconstructed
backwards from today's true total), dashed line forward at the current net
daily rate, shaded band at ±15%.

Horizon is 182 days, plotted weekly.

A vertical rule and labelled dot mark **YOU ARE HERE** with today's real total.

Milestone crossings (25k, 30k, 40k, 50k, 60k, 75k, 100k, 150k, 200k, 250k,
500k, 1M) are **not drawn on the chart** — they surface in the hover tooltip
when you are within 3.5 days of one. They were drawn on the chart originally
and collided into an unreadable mess.

Below it, a caveat paragraph stating in plain English: followers gained,
followers lost, the net, the daily rate, what the dashed line assumes, and the
honest warning that most of this growth comes from car content so it holds only
while that access does.

**Monthly views since August 2025** — bar chart. This exists because views have
no 30-day wall, so it is the only genuine long view available.

**Follower history, banked here** — line chart of the totals this page has
recorded itself, one per day. With fewer than two readings it shows a message
rather than an empty chart.

---

## 3. Content

Reels from the last 7 days, sorted by views descending, capped at 40 rows.

Each row: first line of the caption as the title; date, likes, like rate as a
percentage, and a permalink; a tag; views as a large right-aligned numeral.

Tags by view count:

- `cleared` — 50,000 or more, underlined
- `mid` — 5,000 to 50,000
- `flat` — under 5,000

Section note: reel count, total views, and how many cleared 50k.

---

## 4. Inbox

Threads from the last 24 hours, promotions/social/updates excluded. Subject,
sender display name, relative time, snippet, and a link into Gmail.

Empty state is a real sentence, not a dash: "Nothing new. No brand or outreach
mail in the last 24 hours."

---

## 5. Follow-ups

Threads where his was the last message and 5+ working days have passed, sorted
by most overdue first. Working-day count shown in alert red.

Each row has **Draft a follow-up**, which:

1. `GET /api/gmail/thread/[id]` — fetches the full thread as plain text
2. Takes the last 6 messages, truncated to 1,800 characters each
3. Builds a transcript labelling each message "Elliot" or the sender's name
4. `POST /api/draft` with that transcript, the `STYLE` prompt from
   `01-product.md` and the working-day count; the handler calls Anthropic
   server-side
5. Renders the result in an editable textarea

Then **Save to Gmail** `POST`s to `/api/gmail/draft`, which appends a real
draft to `[Gmail]/Drafts` with `In-Reply-To` and `References` set so it
threads, subject prefixed `Re:` if not already. Or **Copy** to clipboard.

The transcript goes to Anthropic. That is the one place thread contents leave
the app, and it is worth being deliberate about rather than incidental.

Nothing is ever sent from this page. The button says "Save to Gmail" and the
note says "Edit before sending. Nothing is sent from here." Keep both.

The button relabels through the flow: *Draft a follow-up* → *Reading thread* →
*Drafting* → *Redraft*, or *Try again* on failure.
