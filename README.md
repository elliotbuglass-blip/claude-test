# ReelBot 🎬🏎️

Drop in your raw clips → ReelBot cuts them, makes them moody, writes the on-screen text, and posts them as **trial reels**.

## How it works (the simple version)

```
 inbox/          ✂️ EDITOR             🧠 CAPTION WRITER          👀 YOU          📬 POSTER
 your clips  →  finds the rev,     →  reads your stats +    →  quick check  →  trial reel
                crops to 9:16,        competitors, writes      (optional)      goes live
                moody look            3 different hooks
                     ↑                                                            │
                     └──────────── 📊 next time, it learns from the results ──────┘
```

1. **You** drop clips in the `inbox/` folder.
2. **The Editor** finds the best moment (it *listens* for the loudest bit, like a cold start or a rev), cuts an 8-second reel, makes it vertical, and gives it a darker, moody look.
3. **The Caption Writer** (Claude AI) looks at a frame from your clip, your best and worst reels, and your competitors' best posts. Then it writes 3 *different* hooks, one video for each. That's your trial-reel testing method, done automatically.
4. **You** quickly watch them in `output/review/` (you can turn this step off later).
5. **The Poster** uploads them to Instagram as trial reels, so only non-followers see them first.
6. Next run, it pulls fresh stats, so captions keep getting smarter.

## What your stats already say (last 7 days, 49 reels)

| Did great 🔥 | Flopped 🧊 |
|---|---|
| "All black spec… always" **1.33M** (lowest skip rate: 38%) | "No trends here" ~2–4K (posted 4 times) |
| "Aston Martin sounds…." **292K** | "No trending audio" 3K |
| "DB12 cold starts never sounded better" **173K** | "The Aston is the therapy" 2K |
| "Zara doing Barbour dupes now?" **107K** | "Barbour dupes in Zara now???" 3K ← same idea, different words! |
| "There was no other spec really" **105K** | "Tony Soprano is a fashion icon" 1.5K |

**Lessons:** "spec" identity lines win (all black, Bruce Wayne, no other spec). Engine-sound captions win. "Dupe" fashion takes win. Anti-trend captions flop. And the exact wording matters a lot: the same Barbour idea got 35× more views worded one way. That's why testing several captions per clip works.

## Setup (one time)

**Step 1: Install.** You need Python 3.10+ and ffmpeg (Mac: `brew install python ffmpeg`).
```bash
pip install -r requirements.txt
cp .env.example .env
cp config.example.yaml config.yaml
```

**Step 2: Fill in `.env`** (it's like a locked drawer for passwords. It never gets uploaded):
- `ANTHROPIC_API_KEY`: from console.anthropic.com. Runs the caption writer (costs a few cents per clip).
- `WINDSOR_API_KEY`: from your Windsor.ai account. Pulls your Instagram stats.

**Step 3: Get your Instagram posting key** (`IG_ACCESS_TOKEN`). Windsor can read your stats, but it can't post *trial* reels, so this part talks to Instagram directly:
1. Go to developers.facebook.com → **Create App** → type "Business".
2. Add the **Instagram** product, and use Facebook Login for Business.
3. Make sure your Instagram is a Creator/Business account linked to a Facebook Page.
4. In **Graph API Explorer**, pick your app and tick these permissions: `instagram_basic`, `instagram_content_publish`, `pages_show_list`, `pages_read_engagement`, `business_management`.
5. Click **Generate Access Token**, then swap it for a long-lived (60-day) token with the Access Token Debugger's "Extend" button.
6. Paste it into `.env` as `IG_ACCESS_TOKEN`.

**Step 4: Edit `config.yaml`**: add competitor usernames, and choose your audio mode and how many caption variants you want.

## Everyday use

```bash
python -m reelbot stats --refresh   # what's working right now?
python -m reelbot research          # study competitors (do weekly)
python -m reelbot make              # edit everything in inbox/
#   → watch the videos in output/review/
python -m reelbot approve all       # or: approve db12_cold_start__v2
python -m reelbot post              # posts approved videos as trial reels
```

Or do it all at once: `python -m reelbot run`.

**Tips**
- Want to tell the AI what's in a clip? Add a text file with the same name: `db12_night.mp4` + `db12_night.txt` ("triple black DB12, night, London").
- Want to write captions yourself? `python -m reelbot make --captions "All black spec… always|The only choice really"`
- To run it every day automatically, add a cron job on your computer (ask Claude to set it up).

## About trending audio 🎵 (important)

Instagram **does not let any app add sounds from its music library**. Only the Instagram app can. So there are two options:

- **`mode: original`** (default): keep your car's real sound. Your sound-focused reels are already some of your best.
- **`mode: music` / `mix`**: put moody tracks you have the rights to into the `audio/` folder (royalty-free libraries like Artlist or Epidemic Sound). ReelBot picks one and mixes it in. These show up as "original audio", not the trending sound.

If a specific *trending* Instagram sound matters for a reel, set `require_approval: true`, download the finished video from `output/review/`, and post it from the app with the sound added. It takes about 20 seconds.

## Rules it follows on purpose
- Competitor research reads only **public numbers and captions** through Instagram's official API. It never downloads or reuses other people's videos.
- It spaces posts out (`minutes_between_posts`) so the account doesn't look like a spam bot.
