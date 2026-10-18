# ReelBot end-to-end test, with the real Claude AI (18 Oct 2026)

## Headline
The full pipeline now runs with Claude on Elliot's 20 Drive clips: analysis, research, planning, text-spot choice,
colour match and render. **31 reels made, none posted** (posting was monkeypatched to raise).
- **What worked:** every clip was classified correctly (the Zara jacket clips came out as menswear, not DB12). The hooks
  mostly sound like Elliot, and the "Why this reel" panel is filled in and specific.
- **Three planning bugs found and fixed:**
  - Claude cited unposted drafts as "your own winning reels".
  - Hooks quoted timings from the full clip ("Thirteen seconds of calm") on 8-second reels.
  - With 2 reels per clip, Trends and Original reels were never made.
- **Text placement is better but still the weakest part,** mostly in car interiors where the person moves (see Open issues).
- **Claude spend: $2.40.** Apify hit its $5/month limit halfway through.

## Setup
- Fresh storage (scratch), web app in Review mode, 2 reels per clip, default research mix (40/25/15/20). The harness
  (`harness.py` here) runs the app in-process, tracks Claude spend per call with a $4.60 cap, and disables posting.
- `import_drive.run()` imported all 20 clips (11 main, 9 b-roll) with their notes.
- Google Trends and TikTok covers are blocked by this box's network (as expected).
- The Instagram token was **expired at the start and renewed mid-run**: the first 27 reels were planned without
  Elliot's history. After the renewal, history refreshed (150 reels, best hours 16:00 / 11:00 / 15:00) and his colour
  look was learnt from his last 12 reels. The last 4 reels used both.

## What worked
- **Clip analysis (20/20 right).** All 6 changing-room clips were described as menswear ("Black Zara wax-style field
  jacket… mirror selfie try-on in a changing room"), including the 2 with no note. Car clips are specific ("DB12S
  interior shot from the back seat… cold-starting the car"). B-roll kept its folder kind, and the subjects are accurate
  (exhaust, console pan, sill plate, door).
- **Hooks.** Mostly calm, confident, a little cheeky, and all under 8 words. Best ones: "Always let the collar do the talking",
  "Doctor's orders: daily Aston", "Leaving before anyone asks for a lift", "Door shut. World on mute." (an Original
  series, "Do Not Disturb"), "Barbour money stays in my pocket". No jacket reel mentions the car.
- **With Elliot's real history** the plans get much sharper. For example "Dupe Court: Zara stands accused of Barbour"
  (Original series, 68/100) was built on his own dupe winners (656K, 240K, 156K vs a 3.5K median).
- **Why this reel / virality.** Every reel has a score with a reason, 2–4 positives and 1–3 honest negatives, an
  inspired-by line, the source and the sound with a reason. See `2-review-why.png`.
- **Colour.** Natural, slightly dark, deep blacks, not grey, both before and after his colour look was learnt.
- **Text.** Exteriors sit over the dark fence and read well. Jacket clips use the dark curtain.

## Bugs and prompt problems fixed
1. **Unposted drafts cited as evidence.** "HOOKS ALREADY USED" made Claude write "builds on your own winning reel 'Hands
   on the wheel. Wait for it.'" about a draft made a minute earlier. The context now says these aren't posted and
   aren't evidence. Re-test: plans say "No specific research reels were supplied" instead.
2. **Hooks didn't match the reel's cut.** The planner saw frames from the whole clip and its full length, but the reel
   is 8 s cut around the loudest moment, so the start-up lands about 1 s in. That produced "Thirteen seconds of calm. Then this."
   and "Wait for it". Planning now works out the cut first, sees frames only from that part, gets `reel_cut`, and is
   told not to quote full-clip timings. The cut is stored on the reel. Re-test hooks: "Sound on. You'll thank me.",
   "POV: the dealer said 'go on then'".
3. **Trends and Original reels never made.** The mix was split per clip, so 2 reels per clip = 1 Instagram + 1
   TikTok every time. `mix_plan` now gives each reel to the source furthest behind its share over the last 40 reels,
   different within a batch where possible. 10 test batches came out at 8/5/3/4 (= 40/25/15/20). Re-test on 2
   clips gave Original ("Do Not Disturb", "Dupe Court") and Trends (a bold "hot take" experiment, since Google Trends
   is blocked here).
4. **Research relevance too strict.** "Relevant" was judged against the exact clip subject ("black cotton field
   jacket with corduroy collar…"), so 2 topics kept **0 of 12** reels. It now judges the niche (any men's outfit
   or try-on reel for a jacket clip). *Not re-tested, because Apify ran out.*
5. **No topic winners, but Claude still cited "the dominant format in topic research".** An empty list now says
   "(none on topic: don't cite topic winners or formats)".
6. **Text-spot prompt.** It now gets the clip's subject and these rules:
   - don't cover hands or wrists (watch, rings);
   - don't cover the garment in outfit clips;
   - never pick a box that touches a person in any of the 3 moments;
   - if every box does, pick the one clear in the first moment.
   The preview Claude looks at is bigger (480 px per moment, was 360).
7. **Safe zone 62% → 68% of the height.** The dark centre console Elliot likes sits around 60–75% in his interior
   framing, so it was never even a candidate. 68% still keeps clear of a one-line caption.
   **Elliot should confirm**: a long caption covers ~35% of the bottom.
8. **Apify errors were unreadable** ("403 Forbidden"). They now show Apify's message: "Apify 403: Monthly usage hard limit exceeded".
9. **A failed research read threw away the paid Apify result.** That read is now optional: the research is kept without the on-screen text.

## Open issues
- **Apify limit.** The Apify account hit its **$5/month hard limit** after 7 of 11 clips. Each clip runs a fresh
  hashtag scrape (5 tags × 40) plus a TikTok scrape (4 × 30), and small hashtag differences ("barbourdupe" vs
  "barbourstyle") miss the 3-day cache. That's roughly $0.40–0.70 per clip, so at 5 reels a day $5 lasts about a week.
  Raise the limit, cut `per_tag`, or reuse research when most hashtags overlap.
- **Text placement in moving or busy shots.** The text is always one centred line, 76% wide:
  - Push-in mirror selfies: no spot stays clear of the head for 8 s (`8-pushin-no-clear-spot.jpg`). Claude now
    picks the spot that's clear during the hook and says so, but the text still grazes the hair later.
  - Back-seat interior (IMG_8194, IMG_9194): the wheel, screen and forearm fill the frame. 4 of 11 reels now sit on
    the dark console. Others still cross the lower wheel rim or the arm, even though Claude says "below the wheel
    hub" (`7-interior-text-spots.jpg`).
  - Fix worth doing next: let the text sit left or right, not just centred (the console is left of centre in these
    shots), or show the hook only for the first ~3 s when nothing is clear. Elliot can already move it in Review
    ("Move the text").
- **B-roll is still never cut in automatically.** The planner has no b-roll field.
- **Short clips make short reels** (IMG_8952 is 2.8 s). IMG_8957 got only 1 reel in the first batch; Claude returned one plan.
- **Hook ideas lean on two templates.** Two hooks close to Elliot's own "Vitamin A" (#1 topic reel) and two "Barbour
  dupe at Zara?" near-copies of his own TikTok. Both are noted as risks in the negatives. Fine for a trial, but watch it.
- "Licence to cold start" suggests Goldfinger over a cold start, and its own negatives say the music buries the roar.
  Reels like this should keep original audio.

## Claude spend (Opus 5.5, $4 / $20 per M tokens)
| Step | Calls | Cost |
|---|---|---|
| Clip analysis | 20 | $0.39 |
| Reading research reels | 6 | $0.49 |
| Planning | 16 | $0.80 |
| Text-spot choice (incl. 3 re-test rounds) | 78 | $0.73 |
| **Total** | **120** | **$2.40** (417K in / 37K out) |

A normal clip with research costs about $0.12–0.18 (analysis 2¢, research read 8¢, plan 5¢, text 1¢ per reel).

## Every reel
"re-test" = made after the fixes. "history" = also planned with Elliot's real Instagram history.

| Clip | Hook | Source | Score | |
|---|---|---|---|---|
| IMG_8959 | Changing room verdict: obviously yes | instagram | 52 | |
| IMG_8959 | Always let the collar do the talking | tiktok | 55 | |
| IMG_8960 | Zara wax jacket, Barbour energy | instagram | 55 | |
| IMG_8960 | Barbour money stays in my pocket | tiktok | 58 | |
| IMG_8956 | Came in for socks. Left with this. | instagram | 56 | |
| IMG_8956 | Black on black. Zero logos needed. | instagram | 52 | |
| IMG_8958 | Zara did the wax jacket quietly well | instagram | 52 | |
| IMG_8958 | The Barbour dupe everyone's quietly buying | tiktok | 58 | |
| IMG_8958 | Zara wax jacket. Barbour can wait. | instagram | 52 | re-test |
| IMG_8958 | Barbour dupe at Zara? Honestly, yes. | tiktok | 58 | re-test |
| IMG_8957 | The Zara field jacket. Save the code. | instagram | 56 | |
| IMG_8957 | Dupe Court: Zara stands accused of Barbour | original (series "Dupe Court") | 68 | re-test, history |
| IMG_8957 | Unpopular opinion: nobody checks the label | trends (bold experiment) | 55 | re-test, history |
| IMG_8952 | Zara wax jacket. Fitting room approved. | instagram | 52 | |
| IMG_8952 | Always start with the jacket, actually. | tiktok | 58 | |
| IMG_8190 | Doctor's orders: daily Aston | instagram | 56 | |
| IMG_8190 | Not Bond. Same taste, though. | instagram | 49 | |
| IMG_8190 | Door shut. World on mute. | original (series "Do Not Disturb") | 58 | re-test, history |
| IMG_8190 | Hot take: the door is the flex | trends (bold experiment) | 44 | re-test, history |
| IMG_9194 | My neighbours' least favourite alarm clock | instagram | 60 | |
| IMG_9194 | POV: you're in the back. Listen. | instagram | 56 | |
| IMG_9194 | Morning supplement: one cold start | instagram | 58 | re-test |
| IMG_9194 | Licence to cold start | instagram | 46 | re-test |
| IMG_8195 | Hands on the wheel. Wait for it. | instagram | 56 | |
| IMG_8195 | Brown trousers, black Aston. No notes. | instagram | 50 | |
| IMG_8194 | Thirteen seconds of calm. Then this. | instagram | 56 | (bug 2) |
| IMG_8194 | Some men meditate. I press start. | instagram | 52 | |
| IMG_8194 | Sound on. You'll thank me. | instagram | 55 | re-test |
| IMG_8194 | POV: the dealer said 'go on then' | instagram | 50 | re-test |
| IMG_8176 | Dressed to match the car. Obviously. | instagram | 58 | |
| IMG_8176 | Leaving before anyone asks for a lift | instagram | 62 | |

Where TikTok research failed (an Apify 502 on IMG_8956, then the monthly limit), the TikTok reel became an Instagram one, as designed. Reels
planned before the history refresh have no view numbers to cite, so their scores cluster around 50–60.

## Files
- `1-upload-pipeline.png`: Upload page and pipeline, all reels waiting for review
- `2-review-why.png`: Review with "Why this reel" open
- `3-research.png`: Research: best times from history, topic sounds, TikTok table
- `4-settings.png`, `5-library.png`
- `6-reel-frames.jpg`: contact sheet, 3 frames from every reel with clip, source, score and hook
- `7-interior-text-spots.jpg`: interior text after the fixes (2 on the wheel rim, 2 on the console and forearm)
- `8-pushin-no-clear-spot.jpg`: the candidate boxes on a push-in selfie, where none stays clear of the head
- `harness.py`, `sheet.py`: how this run was driven (no keys in them)
