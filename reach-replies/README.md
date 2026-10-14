# Reach & Replies

Elliot's private dashboard: Instagram numbers and the outreach inbox in one place, plus follow-up drafts for threads that have gone quiet. One app does both jobs. It's a **website**, and you can add it to your **iPhone home screen** where it opens full-screen like a normal app.

Read `CLAUDE.md` and `docs/` before changing anything. `docs/03-auth-and-setup.md` covers the hard part.

## What's built

| Tab | What it shows |
|---|---|
| Overview | Follower total (checked every 5 min, and it only ever shows a real reading), 30-day views, 7-day views vs the previous 7, 30-day unique reach, new followers, two charts |
| Growth | Six-month projection (flat 30-day net rate, ±15%), monthly views since Aug 2025, and the follower history this app records |
| Content | Reels from the last 7 days, sorted by views, tagged cleared / mid / flat |
| Inbox | Last 24 hours, with promotions, social and updates filtered out |
| Follow-ups | Threads where you sent the last message 5+ working days ago. Draft → edit → **Save to Gmail**. Nothing is ever sent. |

Everything sits behind one password. The browser only talks to this app. Instagram, Gmail and Anthropic are all called from the server.

## Setup (one evening)

### 1. Instagram (Meta developer app)
Follow `docs/03-auth-and-setup.md` → Instagram. You end up with `IG_APP_ID`, `IG_APP_SECRET`, `IG_USER_ID` and a long-lived `IG_ACCESS_TOKEN`. After that the daily cron keeps the token refreshed.

### 2. Gmail (app password)
On `elliotcameronbusiness@gmail.com`, turn on 2-Step Verification. Then go to **myaccount.google.com/apppasswords**, create one called "Reach & Replies", and copy the 16 characters into `GOOGLE_APP_PASSWORD`.

### 3. Anthropic
Create an API key at console.anthropic.com and put it in `ANTHROPIC_API_KEY`. Drafts cost pennies.

### 4. Deploy to Vercel
1. On vercel.com: **Add New → Project**, import this GitHub repo, and set **Root Directory** to `reach-replies`.
2. **Storage → Create → Postgres (Neon)** and connect it to the project. That sets `DATABASE_URL` for you. The tables create themselves on first use.
3. **Settings → Environment Variables**: add everything from `.env.example`. Use a long password for `APP_PASSWORD` and a random string for `CRON_SECRET`.
4. Deploy.

### 5. Check it works
Sign in, then open `https://<your-app>.vercel.app/api/health`. Every line should say `"ok": true`. If one doesn't, its `detail` says why in plain English. This is build step 1 in `docs/02-architecture.md`, so get it fully green before trusting any number on the page.

### 6. Load the banked history
The prototype recorded 7 days (8–14 Oct 2026: 28,131 → 30,525). Load them once:

```bash
cd reach-replies
DATABASE_URL="<from Vercel>" npm run db:seed
```

Back the table up now and then (`npm run db:backup > backup.json`). Instagram won't give this history back if it's lost.

### 7. Put it on your iPhone
1. Open the site in **Safari** and sign in.
2. Tap **Share** → **Add to Home Screen** → **Add**.
3. It opens full-screen with its own icon and stays signed in for 180 days.

## Local development

```bash
cd reach-replies
cp .env.example .env.local   # fill in
npm install
npm run dev                  # http://localhost:3000
npm test                     # growth maths + formatting
npm run lint                 # typecheck
```

Without `DATABASE_URL` the cache lives in memory and nothing is recorded.

## Still to verify against the live accounts

These couldn't be checked while building. Meta's docs site wasn't reachable from the build environment, and the Instagram connection used there had expired on 13 Oct.

- **Instagram metric names and parameters.** They all sit in one `METRICS` block at the top of `lib/instagram.ts`. Run `/api/health` and fix any Meta rejects there. `docs/04-data.md` describes the approach.
- **Gmail app passwords.** Google keeps tightening them. If the health check says Gmail sign-in failed and the password is definitely right, see the fallbacks in `docs/03-auth-and-setup.md`.

## Why not an App Store app?
This app shows your real inbox and is only for you. An App Store build would need Apple review, a developer account (£79/year) and a privacy policy, all for an audience of one. The home-screen version uses the same code as the website and updates the moment you deploy. If you ever need native features like push notifications, the site can be wrapped with Capacitor later without rewriting it.
