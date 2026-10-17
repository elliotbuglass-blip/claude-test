# ReelBot daily routine (instructions for Claude)

You are running ReelBot inside Claude Code. **You are the brain**: don't use the Anthropic API,
Google Drive OAuth or GitHub Actions. Network secrets add the keys for Apify, Google Drive and
Instagram automatically. Work on branch `claude/trusting-dijkstra-rrizs1`, and commit + push
`data/` at the end of every run (that's the robot's memory between runs).

Check `mode` in `config.yaml`: **review** or **autopilot**.

## Morning run (both modes)
1. **Learn from what I posted.** Run `python -m reelbot results`. It fetches views, reach,
   shares, saves and watch time for every reel ReelBot posted. Also pull my last 14 days of
   stats with the Windsor connector (`instagram`) into `data/my_reels.json`. Compare what
   changed between reels (on-screen text, angle, post caption, track, seconds, text_position)
   against results, and update `data/learnings.md` with what's winning, what's losing, and
   what to test next. Only trust a result after ~24h.
2. **New clips.** Run `python -m reelbot pull`. This also syncs music from the Drive `audio/` subfolder.
3. **Research the topic.** Look at a frame of each new clip and name the subject. Run
   `python -m reelbot topic <3–5 hashtags>`, look at the frames in `output/topic/`, ignore
   reels that aren't really about the subject, and read the on-screen text of the rest. Use
   `competitor_matches` and `trending_sounds` from `data/topic_research.json`.
4. **Plan tomorrow's posts.** Get the times with `python -m reelbot slots <posts_per_day>`.
   Write `data/plan.json` (format at the top of `reelbot/autopilot.py`). One item = one reel.
   Each reel gets its own on-screen hook (under 8 words, no emoji), post caption, angle, and
   anything listed in `autopilot.experiment_with`. Mostly reuse what's winning, but **change
   one thing per reel vs a past winner**, so results teach something. Use every new clip
   before reusing old ones; old clips can be reused with new hooks.
   - **Music:** pick the track from `audio/` whose mood best fits the clip and the trending
     sounds. Also put the matching trending Instagram sound in `sound_suggestion`.

## Then, by mode
- **review:** render each planned reel with `python -m reelbot post-due --dry-run`
  (temporarily set `post_at` to now), send me the videos, and list each one's hook, caption and
  suggested trending sound. Only `schedule` the ones I approve.
- **autopilot:** run `python -m reelbot schedule data/plan.json`. The posting runs post them.

## Posting runs (09:00, 12:00, 15:00, 18:00, 21:00)
Run `python -m reelbot post-due`, then commit + push `data/`. Keep it short; nothing else.

## Mondays (also)
Run `python -m reelbot radar`, read the outlier frames in `output/radar/`, and refresh
`data/research_brief.json` (winning_patterns, avoid, outlier_reads).

## Report (end of the morning run)
Five short lines: yesterday's best and worst reel and why, what's scheduled for tomorrow,
the suggested sound for each, and what's being tested.
