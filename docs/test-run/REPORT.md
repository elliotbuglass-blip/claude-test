# ReelBot end-to-end test run (17 Oct 2026)

## Headline
**The AI half could not run: `ANTHROPIC_API_KEY` is not set in the test environment.** Clip analysis, reel
planning (hooks, captions, sounds, virality score, positives/negatives, "Why this reel"), reading research reels
and the AI text-spot check all need Claude, so none of them were tested. Nothing was faked. Everything else
was tested on the real clips from Drive. To finish the test, add `ANTHROPIC_API_KEY` to the cloud environment and
start a new session, then run `import_drive.run()` inside the app (see below).

## What was run
- New `reelbot/app/import_drive.py`: imports the Drive "Main" (11) and "B-roll" (9 unique) clips into the app with
  their `.txt` notes as descriptions, and kind set from the folder. Safe to run again (skips file names it already has).
  All 20 imported. Drive quirks handled: the duplicate `IMG_8197.MOV` in B-roll is imported once, and notes are matched by name across both folders
  (`IMG_8215.txt` sits in Main, its video in B-roll). To re-run with Claude: start the app, then call `import_drive.run()`.
- Web app in Review mode, 2 reels per clip, Instagram posting monkeypatched to raise (nothing posted).
- Research APIs: Apify Instagram hashtag (10 reels, views + sounds + frames OK) and Apify TikTok (5 videos OK).
  TikTok covers and Google Trends are blocked by this box's network allowlist (known, fine on the server).
- Renderer check without Claude: one reel per main clip through the real `render_reel()` with a placeholder line
  ("Render test, no AI hook yet"), colour `match`, fallback text placement, b-roll cut-ins on 2 reels.
  11/11 rendered, 15–40 s each from 4K. Frames: `7-reel-frames.jpg`.

## What looked right
- Colour: natural, slightly low exposure, deep blacks, not grey or bleak. Car interiors and the changing-room clips both look good.
- Text: small thin white serif, inside Instagram's safe zone, readable on all 11.
- Upload pipeline, Library, Calendar, Research and Settings pages all load.

## Bugs found and fixed
1. **Review page crashed (500)** when a reel had no research snapshot (`res.original_share is not none` is true for a missing key). Now `is number`.
2. **Failed analysis left a clip "analysing" forever** (pipeline showed "⏳ watching the clip…" with no way out). Analysis or planning
   failures now mark the clip `failed` with the reason. The pipeline shows it with "retry in Library", and "Save & re-analyse" on a
   failed clip carries on to making reels.
3. **A restart lost all queued work** (the queue is in memory): clips stuck in analysing and reels stuck in rendering. On start, the app now
   re-queues analysis and renders, and marks clips that were mid "making" as failed so you can make them again.
4. **Expired Instagram token was hidden**: "History refreshed: 0 reels" instead of an error. It now raises
   `Instagram: Error validating access token: Session has expired…`. **The IG access token has expired; it needs renewing before posting/stats work.**
5. Clear error when Claude isn't connected ("Claude isn't connected: add ANTHROPIC_API_KEY…") instead of an SDK auth trace.
6. Cut reason said "(engine/rev)" on non-car clips (Zara jacket). Now neutral.
7. Drive notes had Windows line endings (`\r\n`); normalised on import.

## Open issues
- **Need the Anthropic key** to test hooks, voice, topic handling (the Zara wax-jacket clips must not become "DB12"), b-roll classification, virality panel.
- **Fallback text placement can cover the steering wheel and badge** (`IMG_8195`, `IMG_9194`, see `8-text-over-wheel.jpg`): the darkest+calm
  measure likes the black wheel. The Claude spot check is meant to catch this, so it depends on the key. A better fallback (prefer lower bands, penalise the frame centre) is worth considering.
- **B-roll is never cut in automatically**: the planner has no b-roll field; it only happens if you add it in Review → "Edit or add b-roll".
- Short clips make short reels (`IMG_8952` is 2.8 s → 2.8 s reel) while the DB says 8 s.
- If Claude's research-reading step fails, the paid Apify result for that topic is thrown away (whole `research_topic` fails).
- Mix of placeholder reels from this run sits in the test DB only (scratch storage, not committed).

## Cost
- Claude API: **$0** (no key).
- Apify: two small test calls (10 IG reels + 5 TikToks), a few cents.

## Screenshots
`1-upload-pipeline.png`, `2-library.png`, `3-review-why.png` (Why this reel open; placeholder reels so research parts are empty),
`4-calendar.png`, `5-research.png`, `6-settings.png`, `7-reel-frames.jpg` (contact sheet), `8-text-over-wheel.jpg`.
