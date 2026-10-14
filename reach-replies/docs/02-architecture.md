# Architecture

## Shape

Single-user Next.js app on Vercel. The browser never talks to Instagram,
Gmail or Anthropic — it talks to this app's route handlers, which hold the
credentials.

```
Browser ──► Next.js route handlers (Vercel) ──► Instagram Graph API
                                           ──► Gmail
                                           ──► Anthropic API
                     │
                     └──► Vercel Postgres  (tokens, daily follower snapshots, cache)
```

Why server-side for everything: Instagram access tokens, Gmail credentials and
an Anthropic API key cannot live in client code. There is no way around this
and no "just for now" version of it.

## Why single-user simplifies everything

Because there is exactly one user, the app skips:

- Sign-up, user accounts, a users table
- Per-user token storage and encryption-at-rest schemes
- A Google OAuth consent screen serving strangers
- Session management beyond one shared secret

And gains one requirement: **the app must be locked**. It shows a real inbox.
Put a single password or a Vercel Protection bypass in front of it before it is
reachable on the internet. A middleware check against one env var is enough —
but it must exist from the first deploy, not later.

## File tree

```
app/
  layout.tsx
  page.tsx                      the dashboard shell, tabs
  (middleware.ts lives at the project root — Next.js requires it there)
  api/
    instagram/
      overview/route.ts         30 days: date, views, reach, new followers
      total/route.ts            current followers + media count
      growth/route.ts           30 days: follows + follows-and-unfollows
      long/route.ts             monthly views since Aug 2025
      media/route.ts            last 7 days of reels
    gmail/
      inbox/route.ts            last 24h
      followups/route.ts        sent, last message mine, 5+ working days
      thread/[id]/route.ts      full thread, plain text
      draft/route.ts            POST — create a Gmail draft
    draft/route.ts              POST — Anthropic, generate follow-up text
    cron/snapshot/route.ts      daily follower snapshot
components/
  Tabs.tsx
  Tile.tsx
  LineChart.tsx                 port of prototype lineChart()
  BarChart.tsx                  port of prototype barChart()
  GrowthChart.tsx               port of prototype drawGrowth()
  Row.tsx
  DraftPanel.tsx
lib/
  instagram.ts                  Graph API client + token refresh
  gmail.ts                      mail client
  anthropic.ts                  drafting call
  growth.ts                     net-follower maths, backwards reconstruction, projection
  format.ts                     fmt(), dates, working-day counting
  db.ts
docs/
prototype/
  dashboard.html                reference implementation
```

## Route handler rules

- Every handler returns `{ data }` or `{ error: { code, message } }`. The
  client renders `message` directly, so write it as a plain sentence a
  non-developer reads — see the error copy table in `03-auth-and-setup.md`.
- Never leak an upstream error body to the client. Log it, return a mapped code.
- Cache Instagram responses for 10–15 minutes server-side. The underlying data
  only refreshes daily, so hammering the Graph API gains nothing and risks
  rate limits.
- Gmail is not cached beyond 60 seconds. The point of the inbox tab is that
  it is current.

## Data store

Vercel Postgres. Three tables, that is all:

```sql
create table tokens (
  provider    text primary key,        -- 'instagram' | 'gmail'
  access      text not null,
  refresh     text,
  expires_at  timestamptz,
  updated_at  timestamptz not null default now()
);

create table follower_snapshots (
  day    date primary key,
  total  integer not null
);

create table cache (
  key        text primary key,
  payload    jsonb not null,
  expires_at timestamptz not null
);
```

`follower_snapshots` is the one that matters long-term. Instagram will not
give follower history beyond 30 days, so this table is the only place a real
long record will ever exist. **Back it up.** Losing it cannot be undone.

Seed it with what the prototype already banked rather than starting from zero.

## Cron

`vercel.json`:

```json
{
  "crons": [
    { "path": "/api/cron/snapshot", "schedule": "17 6 * * *" }
  ]
}
```

Daily at 06:17 UTC. Writes today's follower total to `follower_snapshots`.
Make it idempotent — upsert on `day`, so a retry or a manual run does not
create a duplicate or a wrong value.

Protect the route with `CRON_SECRET`; Vercel sends it as a bearer token.

## Environment variables

```
APP_PASSWORD=                 the single gate
CRON_SECRET=

IG_APP_ID=
IG_APP_SECRET=
IG_USER_ID=                   the Instagram Business account id
IG_ACCESS_TOKEN=              long-lived, seeded once, refreshed by the app

GOOGLE_EMAIL=                 elliotcameronbusiness@gmail.com
GOOGLE_APP_PASSWORD=          see 03-auth-and-setup.md for why, not OAuth

ANTHROPIC_API_KEY=
DATABASE_URL=
```

Commit a `.env.example` with these keys and no values.

## Cost

| | |
|---|---|
| Vercel Hobby | £0 — a single-user dashboard is nowhere near the limits |
| Vercel Postgres | £0 on the free tier at this volume |
| Instagram Graph API | £0 |
| Gmail | £0 |
| Anthropic API | pennies — a few follow-up drafts a week |

The only thing that would change this is going multi-user, which is not what
this is.

## Build order

Do not build it tab by tab. Build it in the order that fails fastest:

1. **Auth, both sides, end to end.** Prove you can pull a real Instagram number
   and list one real Gmail thread from a deployed Vercel function. This is
   where the whole project either works or stalls — `03-auth-and-setup.md`
   explains why. Nothing else is worth writing until this is done.
2. The password gate and the database.
3. Overview tab — tiles and the two charts.
4. Growth tab — the maths in `lib/growth.ts`, with tests.
5. Content tab.
6. Inbox, then Follow-ups.
7. Drafting.
8. Cron snapshot, seeded with existing banked data.
