# Reach & Replies

A private dashboard for Elliot Cameron (@elliotcameron._), a Newcastle-based
Instagram content creator and part-time model. It puts his live Instagram
performance and his brand-outreach email pipeline on one page, and drafts
follow-up emails for threads that have gone quiet.

**Single-user application.** One person uses this: Elliot. There is no signup,
no user table, no multi-tenancy. Every architectural decision follows from
that — see `docs/02-architecture.md` before proposing anything that assumes
multiple users.

**It is private.** It shows his Gmail inbox and his outreach pipeline. It must
never be shared with a brand, a dealership or a press office. If a shareable
version is ever wanted, it is a separate build with all email code removed —
not a toggle.

## Read before changing anything

| File | Covers |
|---|---|
| `docs/01-product.md` | What it's for, the non-negotiables, the drafting tone rules |
| `docs/02-architecture.md` | Stack, routes, file tree, env vars, deployment |
| `docs/03-auth-and-setup.md` | Meta app, Google auth, tokens. **The hard part. Read first.** |
| `docs/04-data.md` | Instagram and Gmail fields, what each metric means, the maths |
| `docs/05-features.md` | Tab-by-tab specification |
| `docs/06-design.md` | Visual system — tokens, type, layout, chart rules |
| `docs/07-decisions.md` | What was tried, what broke, why it is the way it is |

## Where this came from

There is a working prototype: `prototype/dashboard.html`, roughly 1,030 lines,
vanilla JS, built as a Claude artifact. It is the **reference for behaviour,
layout, copy and chart rendering** — all of that is settled and should be
carried across rather than redesigned.

What does not carry across is its data layer. The prototype read Instagram and
Gmail through the Claude artifact runtime (`window.claude.use("mcp")`) using
the viewer's own connected accounts. None of that exists outside an artifact.
This build replaces it with the Instagram Graph API and Gmail, called
server-side with credentials this app holds.

Treat the prototype as a spec, not as code to port. Its SVG chart functions
(`lineChart`, `barChart`, `drawGrowth`, `hover`, `niceTop`, `axis`) and its
number formatter (`fmt`) are worth lifting almost verbatim. Its connector
plumbing is worth nothing.

## Stack

- **Next.js** (App Router) on **Vercel**
- **TypeScript**
- No charting library — inline SVG, carried over from the prototype
- **Vercel Postgres** (or Vercel KV) for the daily follower snapshot and tokens
- **Vercel Cron** for the daily snapshot
- Anthropic API for follow-up drafting

## House rules

- Never fake a number. No animated counters inventing movement between real
  readings, no rounding up, no estimates presented as measurements. Figures
  from this page get quoted in emails to press offices. A wrong number here
  becomes a wrong number in an email.
- Lead with views and reach, not follower count.
- Plain English in all copy, including generated drafts. Nothing that sounds
  like a pitch deck.
- Monochrome. One red, reserved for overdue state.
- No secrets in client code. Every third-party call goes through a route
  handler.
- Nothing is ever sent from this app. Drafts are saved to Gmail for review.
