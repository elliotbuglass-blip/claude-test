# ReelBot 🎬🏎️

Drop in your raw clips → ReelBot cuts them, makes them moody, writes the **on-screen hook text** based on what's actually winning, and posts them as **trial reels**.

## How it works (the simple version)

```
  🛰️ RADAR (weekly)                        📖 TEXT READER
  checks 10-20 competitor accounts   →    looks at frames of each winning reel
  finds reels that beat that               and reads the words ON the video
  creator's normal views                   (not the caption under the post)
                │                                    │
                └──────────────┬─────────────────────┘
                               ▼
                    🧠 RESEARCH BRIEF  ←── your own reels (also read on-screen)
                    "these hook patterns win, these flop, here's why"
                               │
  inbox/        ✂️ EDITOR      ▼   ✍️ HOOK WRITER         👀 YOU         📬 POSTER
  your clips →  finds the rev, →   3 different hooks  →  quick check →  trial reels
                9:16, moody        per clip, from the     (optional)
                                   winning patterns
```

1. **The Radar** looks at your competitors' last ~40 reels each. It flags the ones that did *way* better than that creator usually does (5× their normal views, or 3× with real reach). These are "proven" hooks.
2. **The Text Reader** grabs a few frames from each winning reel and has Claude read **the text burned onto the video**. That's the hook people actually see, which is often different from the post caption. It does the same for your own reels.
3. **The Research Brief**: Claude compares the winners against the flops and writes down the patterns ("spec identity flex", "dupe callout", and so on), why they work, and which competitor hooks fit your content. You get a `output/picklist.md` to read.
4. **The Editor** finds the best moment in your clip (it *listens* for the loudest bit, like a rev), cuts an 8-second vertical reel and gives it a moody look.
5. **The Hook Writer** sees a frame of your clip and the research brief, and writes 3 *different* hooks, one video each. That's your trial-reel testing method.
6. **You** check them in `output/review/`, then **the Poster** sends them out as trial reels.

## What your stats already say (last 7 days, 49 reels)

| Did great 🔥 | Flopped 🧊 |
|---|---|
| "All black spec… always" **1.33M** (lowest skip rate: 38%) | "No trends here" ~2–4K (posted 4 times) |
| "Aston Martin sounds…." **292K** | "No trending audio" 3K |
| "DB12 cold starts never sounded better" **173K** | "The Aston is the therapy" 2K |
| "Zara doing Barbour dupes now?" **107K** | "Barbour dupes in Zara now???" 3K ← same idea, different words! |

*(These are your post captions. Run `stats --read-text` once and ReelBot replaces them with what's actually on screen.)*

## Setup (one time)

**Step 1: Install.** You need Python 3.10+ and ffmpeg (Mac: `brew install python ffmpeg`).
```bash
pip install -r requirements.txt
cp .env.example .env
cp config.example.yaml config.yaml
```

**Step 2: Fill in `.env`** (it's a locked drawer for passwords and never gets uploaded):

| Key | What it does | Where to get it | Cost |
|---|---|---|---|
| `ANTHROPIC_API_KEY` | Claude: reads on-screen text, writes the brief and hooks | console.anthropic.com | a few cents per run |
| `WINDSOR_API_KEY` | Your own Instagram stats | your Windsor.ai account | (you have it) |
| `HIKER_API_KEY` | Competitor Radar (views + videos) | hikerapi.com | cents per run |
| `IG_ACCESS_TOKEN` | Posting trial reels (free route) | Step 3 below | free |

**Step 3: Choose how to post** (`posting.backend` in `config.yaml`):

- **`graph`** (free): talks to Instagram directly. Do this once:
  1. developers.facebook.com → **Create App** → "Business". Add the **Instagram** product.
  2. Your Instagram must be a Creator/Business account linked to a Facebook Page.
  3. In **Graph API Explorer**, tick `instagram_basic`, `instagram_content_publish`, `pages_show_list`, `pages_read_engagement`, `business_management`, then click **Generate Access Token**.
  4. Make it last 60 days with the Access Token Debugger's "Extend" button, and paste it into `.env`.
- **`metricool`** (paid plan): schedules through Metricool, which the creator who shared their files uses for trial reels. Fill in the three `METRICOOL_*` keys instead.

**Step 4: Edit `config.yaml`**: add 10-20 competitor usernames (a few big accounts, several mid-size, a few just ahead of you).

## Everyday use

```bash
# Weekly: what's winning out there and on your page?
python -m reelbot stats --refresh --read-text   # your numbers + your on-screen hooks
python -m reelbot research                      # radar + research brief → output/picklist.md

# Whenever you have clips:
python -m reelbot make                          # edits everything in inbox/
#   → watch the videos in output/review/
python -m reelbot approve all                   # or: approve db12_cold_start__v2
python -m reelbot post                          # out they go as trial reels
```

Or do stats → make → post in one go: `python -m reelbot run`.

**Tips**
- Tell the AI what's in a clip by adding a text file with the same name: `db12_night.mp4` + `db12_night.txt` ("triple black DB12, night, London").
- Write the hooks yourself: `python -m reelbot make --captions "All black spec… always|The only choice really"`
- After the first `research` run, look at the "typical views per account" it prints and adjust `abs_floor_views` in `config.yaml` to about the median of your strongest competitor.
- `research --cached` re-scores the last pull without spending HikerAPI credits.
- Every `stats --refresh` saves a snapshot to `data/snapshots.jsonl`, so you can ask Claude things like "is my DB12 trial reel still climbing?"

## About trending audio 🎵

Instagram **does not let any app add sounds from its music library**. Only the Instagram app can. So:

- **`mode: original`** (default): keep your car's real sound. Your sound reels are already some of your best.
- **`mode: music` / `mix`**: put moody tracks you have the rights to into the `audio/` folder. ReelBot loops them to fit and levels their volume.
- For a specific *trending* sound: download the finished video from `output/review/` and post it from the app with the sound added (about 20 seconds).

## Rules it follows on purpose
- The Radar only takes **ideas and hook structures** from competitors, never their footage. It adapts their hooks to *your* clips and never copies a line word for word.
- Emoji are kept out of the burned-in text (video tools can't draw them), but are fine in the post caption.
- It spaces posts out so the account doesn't look like a spam bot.
