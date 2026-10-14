# Auth and setup

This is the part that will take the longest and the part most likely to stall
the project. Read it before writing any code.

Both halves need manual work in a console that Claude Code cannot do for you.
Budget an evening.

---

## Instagram

### What you need

- An Instagram **Business or Creator** account (not personal)
- A Facebook Page linked to it
- A Meta developer app at [developers.facebook.com](https://developers.facebook.com)

### Steps

1. Create a Meta app. Add the Instagram product.
2. Link the Instagram account and its Facebook Page.
3. Request the permissions needed for your own account's insights — these
   include profile and insights read access. For an app in Development mode
   used only by its own admin, **no Meta App Review is required**. That is the
   single most useful fact here: you never submit this app for review, because
   you are the only user and you are the app admin.
4. Generate a token via Graph API Explorer, then exchange it for a
   **long-lived token** (60 days).
5. Store it as `IG_ACCESS_TOKEN`. Get `IG_USER_ID` from
   `/me/accounts` → the page → `instagram_business_account`.

### Token refresh — do not skip this

Long-lived tokens last 60 days and must be refreshed before they expire. A
token that lapses takes the whole dashboard down silently.

Build this into the daily cron: on each run, if the token is within 10 days of
expiry, refresh it and write the new one back to the `tokens` table. Log the
new expiry. Do not rely on the env var after first boot — the database is the
source of truth once the app is running.

### Verify the API surface before implementing

Meta has changed the Instagram API repeatedly, including splitting it into
"Instagram API with Facebook Login" and "Instagram API with Instagram Login",
and replacing `impressions` with `views` during 2025.

**Do not trust metric names in `04-data.md` without checking.** Before writing
`lib/instagram.ts`, open Meta's current Instagram Platform documentation,
confirm the API version, the insights metric names, their valid `period`
values and their date-range limits, and correct `04-data.md` if it is wrong.
Treat that file as what the prototype used, not as a guarantee of what the API
currently accepts.

---

## Gmail — read this before reaching for OAuth

The obvious approach is Google OAuth with the Gmail API. For a single-user
app it is a bad trade, and here is exactly why.

**Google's OAuth consent screen has two states.** In **Testing**, refresh
tokens expire after **7 days**. Every week the app would break and you would
re-authorise by hand. That is not a dashboard, it is a chore.

**Moving to Production removes the 7-day expiry, but requires Google
verification.** Gmail scopes are *restricted*, which is Google's strictest
tier. Verification for restricted scopes means submitting the app, a demo
video, a privacy policy and a justification, and for many apps a third-party
CASA security assessment that costs money and takes weeks. For a dashboard
one person looks at, that is absurd.

**The Workspace escape hatch doesn't apply.** Setting user type to "Internal"
skips verification entirely and has no 7-day limit — but it requires a Google
Workspace account. `elliotcameronbusiness@gmail.com` is a personal Gmail
address, so this route is closed unless a Workspace subscription is bought
(~£5–6/month).

### Use IMAP with an app password instead

For a single-user app this does everything needed and sidesteps the entire
verification problem:

- **Read the inbox** — IMAP `SEARCH` and `FETCH`
- **Read a full thread** — same
- **Create a draft** — IMAP `APPEND` to the `[Gmail]/Drafts` folder with the
  `\Draft` flag, with `In-Reply-To` and `References` headers set so it threads
  correctly

Setup is: enable 2-Step Verification on the Google account, generate an **app
password**, store it as `GOOGLE_APP_PASSWORD`. No OAuth app, no consent
screen, no verification, no expiring tokens.

In Node, `imapflow` for the connection and `mailparser` for parsing are the
sane choices. Build the draft message with `nodemailer`'s MIME composer and
`APPEND` the result rather than sending it.

**Verify app passwords still work before committing to this.** Google has been
progressively restricting them and the policy has moved more than once. If
they have been withdrawn for IMAP, fall back to OAuth in Testing mode and
accept the weekly re-auth, or buy a Workspace seat and use Internal. Check
this first — it determines the whole Gmail layer.

### Threading a draft correctly

A draft that does not thread is worse than useless, because it looks like a
cold email to the recipient. Set:

- `In-Reply-To:` the `Message-ID` of the message being replied to
- `References:` the existing References chain plus that `Message-ID`
- Subject prefixed `Re: ` unless it already starts with one

---

## The app password gate

Before the first public deploy, put a check in `middleware.ts` comparing a
cookie against `APP_PASSWORD`, with a minimal sign-in page. This app renders
a real inbox. A Vercel URL is guessable and indexable.

Alternatively use Vercel's own Deployment Protection. Either is fine. Having
neither is not.

---

## Error copy

Carried from the prototype. These are read by Elliot, not by a developer —
keep them plain sentences.

| Situation | Shown as |
|---|---|
| Instagram token expired | The Instagram connection has lapsed. Re-authorise it in settings. |
| Instagram rate limited | Instagram is rate-limiting us. Try again in a few minutes. |
| Instagram returned nothing | No data came back from Instagram for that period. |
| Gmail auth failed | The Gmail connection isn't working. Check the app password. |
| Gmail unreachable | Couldn't reach Gmail. Try again in a moment. |
| Drafting failed | Couldn't write a draft just now. Try again. |
| Anything else | That didn't load. |

Never surface a raw upstream error, a stack trace or an HTTP status to the UI.
