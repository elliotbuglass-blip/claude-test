# ReelBot 🎬🏎️

Drop raw clips into a Google Drive folder → ReelBot edits them, writes the **on-screen hook** from what's actually winning, and posts them as **trial reels**. It all runs in the cloud. Nothing gets installed on your computer.

## How it works

```
📱 YOU (phone or browser)                 ☁️ GITHUB (does the work on a timer)
─────────────────────────                 ───────────────────────────────────
Drop clips in Drive  ReelBot/inbox   →    every morning: checks your stats, edits new
                                          clips, writes 3 different hooks per clip
Watch them in        ReelBot/review  ←    finished videos land here
Drag good ones to    ReelBot/approved →   every 3 hours: posts the next one as a trial reel
They end up in       ReelBot/posted  ←
Read on Mondays      ReelBot/picklist.md ← Competitor Radar: what's winning and why
```

**What the robot does inside:**
- **The Radar** (Mondays) checks 10-20 competitor accounts and finds reels that did way better than that creator usually does.
- **The Text Reader** looks at frames of those reels, and of yours, and reads the words **on the video**, not the post caption.
- **The Research Brief** writes down which hook patterns win, which flop, and why.
- **The Editor** finds the rev or cold start in your clip, cuts 8 seconds, makes it vertical and moody, and burns on the hook.

## Setup (one time, all in your web browser)

### 1. Make the GitHub repo private (2 min)
github.com/elliotbuglass-blip/claude-test → **Settings** → scroll to the bottom → **Change visibility** → **Private**.

### 2. Make your Drive folder (2 min)
In Google Drive, make a folder called **ReelBot**. Open it and copy the long code at the end of the web address, after `folders/`. That's your **DRIVE_FOLDER_ID**. The robot creates the subfolders itself on its first run.

### 3. Let the robot into your Drive (15 min, once)
This gives the robot a "key" to your Drive. Everything happens on Google's websites.
1. Go to **console.cloud.google.com** → create a project called `ReelBot`.
2. Search **"Google Drive API"** → **Enable**.
3. Open **Google Auth Platform** (also called "OAuth consent screen") → **Get started**. App name `ReelBot`, your email, Audience **External**.
4. **Audience** → **Publish app** (set it to *In production*). Otherwise the key stops working after 7 days.
5. **Clients** → **Create client** → type **Web application**. Under *Authorised redirect URIs*, add `https://developers.google.com/oauthplayground`. Copy the **Client ID** and **Client secret**.
6. Go to **developers.google.com/oauthplayground** → ⚙️ (top right) → tick **Use your own OAuth credentials** → paste the ID and secret.
7. In the box on the left, type `https://www.googleapis.com/auth/drive` → **Authorize APIs** → choose your Google account. If you see *"Google hasn't verified this app"*, click **Advanced → Go to ReelBot**. That's fine, because it's your own app.
8. Click **Exchange authorization code for tokens** → copy the **Refresh token**.

### 4. Get your other keys
| Key | What it unlocks | Where |
|---|---|---|
| `ANTHROPIC_API_KEY` | Claude: hooks, reading on-screen text, research | console.anthropic.com → API Keys (add about $5 credit) |
| `WINDSOR_API_KEY` | Your Instagram stats | your Windsor.ai account |
| `HIKER_API_KEY` | Competitor Radar | hikerapi.com (add a few dollars) |
| `IG_USER_ID` | Which account to post to | `17841400621094281` (that's yours) |
| `IG_ACCESS_TOKEN` | Posting trial reels | see "Posting key" below |

### 5. Put all the keys into GitHub (5 min)
Repo → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**. Add each one, using the name exactly as written:

`ANTHROPIC_API_KEY`, `WINDSOR_API_KEY`, `HIKER_API_KEY`, `IG_USER_ID`, `IG_ACCESS_TOKEN`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REFRESH_TOKEN`, `DRIVE_FOLDER_ID`

Secrets are locked. Even you can't read them back after saving, and they never show up in the code.

### 6. Add your competitors
Open `config.yaml` on GitHub → ✏️ pencil icon → replace the two example usernames with 10-20 real ones → **Commit changes**.

### 7. Press go
Repo → **Actions** tab → **ReelBot** → **Run workflow** → pick `daily` → green button. Click the run to watch it work. After that it runs by itself.

## Posting key (`IG_ACCESS_TOKEN`)
1. developers.facebook.com → **Create App** → "Business". Add the **Instagram** product.
2. Your Instagram must be a Creator/Business account linked to a Facebook Page.
3. **Graph API Explorer** → tick `instagram_basic`, `instagram_content_publish`, `pages_show_list`, `pages_read_engagement`, `business_management` → **Generate Access Token**.
4. **Access Token Debugger** → **Extend** (lasts 60 days) → paste it as the GitHub secret.

⏰ This key runs out after 60 days, so set a reminder to repeat step 4. Until you have it, everything else still works. Just post the videos from `review/` yourself.

*(Prefer Metricool? Set `backend: metricool` in `config.yaml` and add `METRICOOL_API_TOKEN`, `METRICOOL_USER_ID` and `METRICOOL_BLOG_ID` as secrets instead.)*

## Everyday use
- **Add a clip:** upload it to `ReelBot/inbox` from your phone's Drive app. To tell the AI what's in it, add a text file with the same name (`db12_night.mp4` + `db12_night.txt`).
- **Approve:** watch videos in `review/` and drag the good ones to `approved/`. The hook and caption are in each file's **description** (ⓘ details panel). Delete the ones you don't want.
- **Want it now?** Actions tab → Run workflow → choose `make-only`, `post-only` or `research`.
- **Change settings** (clip length, audio, posting times): edit `config.yaml` on GitHub.

## When it runs (UK time, summer)
| When | What |
|---|---|
| 07:40 daily | stats → edit new clips → post 1 approved video |
| 10:40, 13:40, 16:40, 19:40, 22:40 | post the next approved video |
| Mondays 07:10 | Competitor Radar + research brief → `picklist.md` |

## About trending audio 🎵
Instagram doesn't let any app add sounds from its music library. Only the Instagram app can.
- `mode: original` (default): keep the engine sound. Your sound reels already do great.
- `mode: music` / `mix`: put tracks you have the rights to in `ReelBot/audio`.
- For a specific *trending* sound: download the video from `review/` and post it from the Instagram app with the sound added.

## Rules it follows on purpose
- It takes **ideas and hook structures** from competitors, never their footage, and never copies a line word for word.
- Emoji stay out of the burned-in text (video tools can't draw them), but are fine in the post caption.
- It posts at most one video per run, spaced about 3 hours apart, so the account doesn't look like a spam bot.
