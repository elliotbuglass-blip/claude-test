# Putting ReelBot online (Railway)

ReelBot runs on **Railway**, a website that keeps small apps running 24/7. Cost: about **$5/month** (Hobby plan).

## 1. Get your keys ready
| Key | Where |
|---|---|
| `ANTHROPIC_API_KEY` | console.anthropic.com → Get API key → name it **ReelBot-server** (each reel costs pennies) |
| `IG_ACCESS_TOKEN` | Your **Page token** (never expires): Graph API Explorer → extended token → `me/accounts` → Elliot Cameron's `access_token` |
| `IG_USER_ID` | `17841400621094281` |
| `APIFY_TOKEN` | apify.com → Settings → API & Integrations |
| `APP_PASSWORD` | make one up: it's your login for the ReelBot website |

## 2. Create the app on Railway
1. Go to **railway.app** → sign in with GitHub.
2. **New Project** → **Deploy from GitHub repo** → pick **claude-test**.
3. Open the new service → **Settings** → **Source** → set the branch to `claude/trusting-dijkstra-rrizs1`.
   Railway finds the `Dockerfile` by itself.

## 3. Add the keys
Service → **Variables** → **+ New Variable** → add each key from step 1 (name exactly as written).

## 4. Give it a memory (important)
Service → **Settings** → **Volumes** → **+ Add volume** → mount path: `/data`.
This keeps your clips, reels and results safe when the app restarts.

## 5. Get your web address
Service → **Settings** → **Networking** → **Generate domain**.
Open it on your phone → sign in with your `APP_PASSWORD` → add it to your home screen.

## Every ~90 days
The Instagram Page token never expires, but Meta asks you to re-confirm data access about every 90 days:
open the Graph API Explorer once, pick the ReelBot app and press Generate Access Token. Nothing to paste.
