# Data

> **Verify before implementing.** The metric names below are what the working
> prototype used through a third-party connector. Meta has changed the
> Instagram API repeatedly — `impressions` became `views` during 2025, and the
> platform was split into Facebook-Login and Instagram-Login variants. Confirm
> every metric name, `period` value and date limit against Meta's current
> Instagram Platform docs before writing `lib/instagram.ts`, and correct this
> file where it is wrong. The *semantics* below are the valuable part and do
> not change; the field names might.

## The five reads

| Purpose | Needs | Range |
|---|---|---|
| Overview | daily views, reach, new followers | last 30 days |
| Follower total | current followers, media count | now |
| Growth | daily new follows, follows-and-unfollows | last 30 days |
| Long view | daily views | Aug 2025 → today, aggregated monthly |
| Content | per-reel views, likes, caption, permalink | last 7 days |

## Field meanings — read before touching any calculation

These names are misleading and have already caused real bugs.

**`follower_count`** (insights metric) — gross **new** follows on that day.
Not a running total. Instagram caps this at **30 days** of history, hard.

**`followers_count`** (profile field, with the s) — the current total,
**right now**. No history at all. This is why the app banks its own.

**`follows_and_unfollows`** — total follow *and* unfollow activity for the
day, as one combined number.

**`views`** — total plays, not unique. Replaced `impressions`.

**`reach`** — unique accounts. Always lower than views.

## Net follower growth

Instagram gives gross follows and combined activity, never net:

```
net = (2 × follower_count) − follows_and_unfollows
```

Because `follows_and_unfollows = follows + unfollows` and
`follower_count = follows`, so `unfollows = activity − follows`, and
`net = follows − unfollows = 2·follows − activity`.

```ts
const net = clean.map(r => {
  const gross = r.followerCount ?? 0;
  const activity = r.followsAndUnfollows ?? 0;
  return activity ? (2 * gross - activity) : gross;
});
```

Fall back to gross when activity is zero — that means the field was absent,
not that nobody unfollowed.

**Filter out rows where both are zero** before any maths. Those are reporting
gaps, not quiet days, and left in they drag the average down and flatten the
projection.

Put this in `lib/growth.ts` with unit tests. It is the one piece of real logic
in the app and it is quietly easy to get wrong.

## The 30-day history wall

Instagram will not return follower history beyond 30 days. No query rewriting
fixes it. Two consequences:

**1. Historical followers are reconstructed, not fetched.** Take today's true
total and walk *backwards* day by day subtracting net movement. This anchors
the curve to a real number at the right-hand end, where anyone reading it
looks. Force the final point to exactly today's total.

Never walk forwards from an estimated start — that puts the accumulated error
at today, which is the one number that has to be right.

**2. The app banks its own history.** The daily cron writes the current total
to `follower_snapshots`. That table is the only place a genuine long record
will ever exist. Seed it from what the prototype already banked, and back it
up — losing it cannot be undone.

Views have no such limit, which is why the long view chart is monthly **views**
since August 2025 rather than followers.

## Fetching the long view

Insights requests are limited to a short window per call, so going back to
August 2025 means paging in roughly 30-day windows — about 14 requests.

Do this once and cache it permanently. Historical months never change. Only
the current month needs re-fetching, and only daily. Rebuilding the whole
series on every page load will hit rate limits and makes the Growth tab slow
for no reason.

## Rate limits

The Graph API limits calls per app per hour. A single-user dashboard will not
approach this if responses are cached server-side for 10–15 minutes — and
since the underlying data only refreshes daily, caching costs nothing.

It *will* hit limits if every page load re-fetches 14 months of history. See
above.

## Gmail

| Need | How |
|---|---|
| Inbox, last 24h | IMAP `SEARCH` on `INBOX`, `SINCE` yesterday |
| Follow-up sweep | IMAP `SEARCH` on `[Gmail]/All Mail`, messages from self, last 120 days |
| Full thread | Fetch by `Message-ID` / `References` chain |
| Save a draft | `APPEND` to `[Gmail]/Drafts` with the `\Draft` flag |

Gmail's IMAP exposes labels as folders. `[Gmail]/All Mail` and
`[Gmail]/Drafts` are the two that matter. Category tabs (Promotions, Social,
Updates) appear as labels — exclude them from the inbox view as the prototype
did.

### The follow-up rule

A thread is owed a follow-up when:

1. The **last** message in it was sent by Elliot, and
2. At least **5 working days** have passed since.

Working days, not calendar days. A Friday email chased on Monday is not a
chase. The prototype's `workingDaysBetween()` counts forward excluding
Saturdays and Sundays — carry it over as-is.

Sort most-overdue first.

### Threading

Gmail does not expose a stable thread id over IMAP the way the API does.
Reconstruct threads from the `References` and `In-Reply-To` headers, falling
back to normalised subject plus participants. Get this right before building
the Follow-ups tab — the whole tab depends on correctly identifying the last
message in a conversation.

---

## As built (Oct 2026) — differences from the prototype

Recorded here so the next person doesn't re-derive them.

- **Per-day `total_value` reads.** On current Graph API versions `views` (and
  `follows_and_unfollows`) are account-level `metric_type=total_value` metrics,
  not daily time series. `lib/instagram.ts` reads each day as its own one-day
  window and caches it. Days older than 3 days are treated as settled (insights
  can lag ~48h) and cached for good, so a normal load costs a handful of calls,
  not 60. `follower_count` is still read as a daily time series.
- **`follows_and_unfollows`** is requested with `breakdown=follow_type`. The
  combined figure is the sum of the breakdown values. The net formula above is
  unchanged.
- **30-day reach is one window read, not a sum.** The prototype added up daily
  reach and labelled it "unique accounts". That double-counts anyone reached on
  more than one day. The tile now shows a single 30-day `total_value` reading.
- **Long view.** Each month is read in windows of 30 days or less (1st–15th,
  16th–end). Completed months are cached for ten years; the current month every 6h.
- **Gmail threads use `X-GM-THRID`.** Gmail does expose its thread id over IMAP
  (the `X-GM-EXT-1` extension; imapflow's `threadId`). That is the same id the
  web UI uses, so threads are grouped by it instead of rebuilt from
  `References`. It also gives a working "Open in Gmail" link.
- **Mailboxes found by special-use flag** (`\All`, `\Drafts`), not by name.
  Older UK accounts use `[Google Mail]/…`.
- **Draft recipients and threading headers are worked out on the server** from
  the thread itself. The browser only sends the thread id and the edited body.

**Unverified:** the metric names above were written from knowledge of the API,
not checked live. Meta's docs weren't reachable at build time and the test
token had expired. `/api/health` exercises every read, so run it after the
first deploy and correct `METRICS` in `lib/instagram.ts` if Meta rejects one.
