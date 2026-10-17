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
3. **Research this batch's topic.** Look at a frame of each new clip and name the subject
   (e.g. "Aston Martin DB12, night, moody"). Pick 3–5 hashtags for it (e.g. `astonmartin db12
   supercar`) and run `python -m reelbot topic astonmartin db12 supercar`. Look at the frames in
   `output/topic/`, **ignore reels that aren't really about the subject** (hashtags attract junk),
   and read the on-screen text of the rest. Also use `competitor_matches` (my creators' outliers
   on the same topic) and `trending_sounds` from `data/topic_research.json`.
4. **Write hooks.** For each clip in `inbox/`, extract a frame
   (`ffmpeg -ss 2 -i CLIP -frames:v 1 -vf scale=540:-2 frame.jpg`) and look at it.
   Write `variants_per_clip` (config.yaml) on-screen hooks, each a different angle,
   based on the topic research, `data/research_brief.json`, `data/learnings.md` and the account's
   own top reels. Keep each under 8 words, with no emoji or hashtags. For each video, pick the
   trending sound that best fits its mood. Instagram doesn't let apps add library sounds, so
   **list it in the report** for me to add in the app.
5. **Edit.** For each clip, run `python -m reelbot make --captions "hook 1|hook 2|hook 3"`.
   This takes one clip at a time: move other clips out of `inbox/` temporarily,
   or run it once per clip.
6. **Post.** Run `python -m reelbot post`. It posts up to `max_posts_per_run` trial reels.
   Append what was posted to `data/post_log.json`.
7. **Save memory.** Commit and push `data/` and `config.yaml`.
8. **Report.** Write a 5-line summary: what was posted, yesterday's winners and losers,
   what changes tomorrow, and the suggested sound for each new video.

## Every Monday (also)
Run `python -m reelbot radar`. Look at the frames in `output/radar/`, read each
outlier's on-screen text yourself, and write `data/research_brief.json` with keys
`winning_patterns` [{pattern, why_it_works, examples}], `avoid` [..] and
`outlier_reads` [{code, why_it_won, fits_me, fit_reason}].
