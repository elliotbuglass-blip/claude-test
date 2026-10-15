# Decisions and failures

Things that were tried and broke, or were weighed and rejected. Each of these
looks like an easy call from the outside. They are not.

The first group are decisions made for **this build**. The rest came out of the
prototype and still apply.

---

## Rebuilt as a real app rather than ported

**Why.** The prototype read Instagram and Gmail through the Claude artifact
runtime, using the viewer's own connected accounts. Outside an artifact,
`window.claude` does not exist. There is no partial version of this — the
entire data layer is replaced.

What carries over: layout, copy, chart rendering, number formatting, the
growth maths, the drafting prompt. What does not: every line of connector
plumbing.

---

## Follow-up drafting removed (Oct 2026)

**Why.** It was the only part of the app with a running cost (Anthropic API,
pay per use). Elliot chose a free app over in-app drafts. The Follow-ups tab
still lists overdue threads with a link into Gmail. Removing it also made the
Gmail connection read-only.

**If it comes back,** the tone rules in `01-product.md` and the flow in
`05-features.md` still describe it; the previous implementation is in git
history (`lib/anthropic.ts`, `app/api/draft`, `app/api/gmail/draft`).

---

## Single-user, deliberately

**Why.** One person uses this. Multi-tenancy would add user accounts, per-user
token storage and — the real cost — a Google OAuth consent screen serving
strangers, which drags Gmail's restricted scopes into full verification.

**Don't** add a users table "for later". If it ever becomes a product for other
creators, that is a different application with a different auth model, and
building half of it now buys nothing.

---

## IMAP and an app password, not Gmail OAuth

**Why.** Google's OAuth consent screen expires refresh tokens after 7 days in
Testing mode, which means re-authorising by hand every week. Moving to
Production removes that, but Gmail scopes are *restricted* — Google's
strictest tier — so it needs verification, a privacy policy, a demo video and
often a paid third-party security assessment. For a dashboard one person looks
at, that is absurd.

The Workspace "Internal" user type would skip all of it, but requires a paid
Workspace account and the address here is personal Gmail.

IMAP with an app password reads mail and appends drafts with none of that.

**Caveat.** Google keeps tightening app passwords. Verify they still work for
IMAP before committing. If they have gone, the fallbacks are OAuth in Testing
mode with weekly re-auth, or a Workspace seat.

---

## Instagram Graph API direct, not a third-party connector

**Why.** The prototype used Windsor.ai on a trial plan, which refreshed daily
and would need a paid tier for a live app. Going direct to Meta is free, has
no middleman, and — because the app is only ever used by its own admin — needs
no Meta App Review.

**Cost.** More setup once: a Meta developer app, a Business account linked to
a Facebook Page, and a 60-day token that the app must refresh itself. Build
the refresh into the daily cron from the start; a lapsed token takes the whole
dashboard down silently.

---

## Gmail consent raced and failed silently (prototype)

**What happened.** Capabilities asked for consent lazily, at first use. Both
connectors fired on page load, two consent dialogs raced, the platform showed
one, and the other failed with a retryable error that surfaced as nothing at
all. Gmail sections were just empty.

**Lesson for this build.** It no longer applies directly — there is no consent
dialog. But the underlying lesson does: when two async dependencies can fail
independently, make the failure visible. Every route handler returns a mapped
error code and the UI renders it. Nothing fails to an empty state.

---

## The projection was uselessly wide

**What happened.** The forecast used the best and worst 7-day windows in the
last 30 days as its bounds. With one viral week in the sample, the range
spanned from barely-growing to absurd. Elliot's words: *"the projection is far
too broad."*

**Fix.** Flat 30-day average net rate, ±15% band. Boring and defensible.

**Don't.** Reintroduce variance-based bounds, or fit a curve. The data is
30 points of noisy daily movement — it does not support anything cleverer
than a straight line, and a confident-looking curve is a lie.

---

## Milestone labels collided

**What happened.** Milestone crossings (50k, 100k…) were drawn as labelled
points on the projection line. At six months several land close together and
the labels overlapped into mush. Elliot: *"Thers overlapping numbers and now
looks very messy."*

**Fix.** Milestones moved into the hover tooltip only, shown when within
3.5 days of a crossing.

**Don't.** Put them back on the chart, including as rotated or staggered
labels. It was tried.

---

## A live follower counter — rejected in the prototype, now possible

**What happened.** Asked whether the follower total could tick live. Through
the old connector it could not — data refreshed daily, so the only way to make
the number move was to interpolate between readings. Not built, because an
animated ticker inventing movement between real readings puts a fabricated
number on a page whose figures get quoted to brands.

**What changes here.** Calling the Graph API directly, the profile
`followers_count` field is current at the moment of the call. Polling it every
few minutes and updating when it genuinely changes is honest.

**If built, the rule is absolute: only ever show a number that was read.** No
easing between values, no counting up through numbers that were never true, no
extrapolating between polls. A number that animates upward through 30,122 and
30,123 when the reading jumped from 30,121 to 30,124 has displayed two figures
that never existed. Step to the new value, or animate only the transition of a
value that is already real.

Daily *new followers* stays daily regardless — that comes from insights, not
the profile field, and no polling changes it.

---

## Reconstructing follower history

**What happened.** Instagram refuses follower history beyond 30 days —
`last_1y` is rejected, not truncated.

**Fix.** Two things. The 30-day curve is walked *backwards* from today's real
total subtracting net daily movement, so the right-hand end — the end anyone
reads — is anchored to truth. And the page banks the current total to `db`
once a day so a real record accrues going forward.

**Don't.** Walk forwards from an estimated starting point. It puts the error at
today's end, which is the one number that has to be right.

---

## Rows where everything is zero

**What happened.** Days with `follower_count` and `follows_and_unfollows` both
zero are reporting gaps, not quiet days. Left in, they drag the average rate
down and flatten the projection.

**Fix.** Filtered before any calculation.

---

## Things deliberately not done

- **No charting library.** Inline SVG is a few hundred lines and matches the
  design exactly. A library would fight the hairline aesthetic the whole way.
- **No component library.** The design is hairlines and type. Bringing in a UI
  kit means fighting its defaults on every surface. Plain CSS, tokens on
  `:root`, as the prototype does.
- **No sending from the page.** Drafts are saved to Gmail for review. An email
  to a press office is not something to fire off from a dashboard.
- **No brand-facing mode behind a toggle.** A toggle is one misclick from
  showing a dealership the rest of his pipeline. If a shareable version is
  wanted it is a separate build with no email code in it at all.
