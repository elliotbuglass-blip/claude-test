# ReelBot daily routine (instructions for Claude)

You are running ReelBot inside Claude Code. **You are the brain**: don't use the
Anthropic API, Google Drive OAuth or GitHub Actions. Network secrets add the keys for
Apify, Google Drive and Instagram automatically. Work on branch
`claude/trusting-dijkstra-rrizs1` and commit `data/` changes back to it at the end.

## Every day
1. **Learn.** Pull the last 14 days of reel stats with the Windsor connector
   (`instagram`: media_id, timestamp, media_caption, media_views,
   media_reel_skip_rate, media_shares, media_saved). Save them to `data/my_reels.json`.
   Compare reels posted by ReelBot (`output/posted/*.json` and `data/post_log.json`)
   by on-screen hook and angle. Note in `data/learnings.md` which angles won and lost.
2. **New clips.** Run `python -m reelbot pull`.
3. **Write hooks.** For each clip in `inbox/`, extract a frame
   (`ffmpeg -ss 2 -i CLIP -frames:v 1 -vf scale=540:-2 frame.jpg`) and look at it.
   Write `variants_per_clip` (config.yaml) on-screen hooks, each a different angle,
   based on `data/research_brief.json`, `data/learnings.md` and the account's own top
   reels. Keep each under 8 words, with no emoji or hashtags.
4. **Edit.** For each clip, run `python -m reelbot make --captions "hook 1|hook 2|hook 3"`.
   This takes one clip at a time: move other clips out of `inbox/` temporarily,
   or run it once per clip.
5. **Post.** Run `python -m reelbot post`. It posts up to `max_posts_per_run` trial reels.
   Append what was posted to `data/post_log.json`.
6. **Save memory.** Commit and push `data/` and `config.yaml`.
7. **Report.** Write a 5-line summary: what was posted, yesterday's winners and losers,
   what changes tomorrow.

## Every Monday (also)
Run `python -m reelbot radar`. Look at the frames in `output/radar/`, read each
outlier's on-screen text yourself, and write `data/research_brief.json` with keys
`winning_patterns` [{pattern, why_it_works, examples}], `avoid` [..] and
`outlier_reads` [{code, why_it_won, fits_me, fit_reason}].
