"""ReelBot's brain: Claude looks at clips, decides main vs b-roll, and plans reels with a virality score."""

import base64
import json
import os

import anthropic

from ..settings import claude, claude_key

MODEL = "claude-opus-5-5"


def _images(frames):
    return [{"type": "image", "source": {"type": "base64", "media_type": "image/jpeg",
                                         "data": base64.standard_b64encode(f).decode()}} for f in frames]


def _ask(content, schema, system=None, effort="medium", max_tokens=16000):
    if not claude_key():
        raise RuntimeError("Claude isn't connected: add ANTHROPIC_API_KEY to the server's settings, then retry.")
    client = claude()
    kwargs = {"system": system} if system else {}
    response = client.beta.messages.create(
        model=MODEL,
        max_tokens=max_tokens,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        output_config={"effort": effort, "format": {"type": "json_schema", "schema": schema}},
        messages=[{"role": "user", "content": content}],
        **kwargs,
    )
    if response.stop_reason == "refusal":
        raise RuntimeError("Claude declined this request.")
    return json.loads(next(b.text for b in response.content if b.type == "text"))


CLIP_SCHEMA = {
    "type": "object",
    "properties": {
        "kind": {"type": "string", "enum": ["main", "broll"]},
        "kind_reason": {"type": "string"},
        "subject": {"type": "string"},
        "hashtags": {"type": "array", "items": {"type": "string"}},
        "mood": {"type": "string"},
        "highlight": {"type": "string"},
        "search_terms": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["kind", "kind_reason", "subject", "hashtags", "mood", "highlight", "search_terms"],
    "additionalProperties": False,
}


def analyse_clip(frames, duration, has_audio, loud_moment, niche, description=""):
    """Work out what a clip shows, and whether it can stand alone (main) or is a cut-in (b-roll)."""
    said = f'\nThe creator describes this clip as: "{description}". Trust this for anything you can\'t see (names, models, brands, purpose).\n' if description else ""
    text = f"""These are frames (in time order) from one raw clip for an Instagram creator. Their account in general: {niche}
{said}
Clip facts: {duration:.1f}s long, {"has sound" if has_audio else "no sound"}, loudest moment around {loud_moment:.1f}s.

Describe THIS clip as it really is. Don't assume it's the creator's usual subject: a clip can be an outfit, a different
car, a watch, a place, a lifestyle moment. Subject and hashtags must fit what's actually in it.

- kind: "main" if it can carry a reel on its own (a walk-up, start-up, drive, POV, outfit reveal, a moment with a payoff).
  "broll" if it's a short detail or filler shot (a door handle, badge, watch close-up, fabric detail) that only works cut into another clip.
- kind_reason: one short line.
- subject: what it shows, specifically, e.g. "black Aston Martin DB12, start-up from the driver's seat, overcast day"
  or "navy double-breasted suit, mirror outfit check in a hallway".
- hashtags: 3–5 Instagram hashtags (no #) to research what similar reels are doing, specific to general,
  e.g. ["astonmartindb12", "db12", "astonmartin", "supercar"] or ["doublebreastedsuit", "menswear", "mensstyle"].
- mood: 2–4 words for music matching, e.g. "dark, confident, calm".
- highlight: the best moment in one line (e.g. "engine fires up at ~10s").
- search_terms: 2–3 short phrases people type into Google or YouTube about what's in this clip, general enough to
  have lots of searches, e.g. ["aston martin db12", "db12 sound"] or ["double breasted suit", "wedding guest outfit men"]."""
    return _ask([*_images(frames), {"type": "text", "text": text}], CLIP_SCHEMA, effort="low", max_tokens=4000)


READ_SCHEMA = {
    "type": "object",
    "properties": {"reels": {"type": "array", "items": {
        "type": "object",
        "properties": {"code": {"type": "string"}, "on_screen_text": {"type": "string"},
                       "relevant": {"type": "boolean"}},
        "required": ["code", "on_screen_text", "relevant"], "additionalProperties": False}}},
    "required": ["reels"],
    "additionalProperties": False,
}


def read_reels(reels, subject):
    """Read the burned-in text of several research reels in one go, and drop off-topic ones."""
    content = []
    for r in reels:
        if not r.get("frame_bytes"):
            continue
        content.append({"type": "text", "text": f"Reel code {r['code']} ({r['views']:,} views):"})
        content += _images(r["frame_bytes"])
    content.append({"type": "text", "text": f"""For each reel code above:
- on_screen_text: the text edited onto the video, word for word (empty if none). Ignore Instagram's UI, watermarks, number plates and signs in the scene.
- relevant: true if the reel is in the same niche as this clip, so its hook, format or sound could carry over: {subject}.
  Judge the niche, not the exact item (for a men's jacket try-on, any men's outfit, try-on or styling reel counts; for a
  supercar clip, any car reel). False for junk the hashtags attract (house listings, memes, ads, unrelated topics)."""})
    return _ask(content, READ_SCHEMA, effort="low", max_tokens=8000)["reels"]


PLAN_SCHEMA = {
    "type": "object",
    "properties": {"reels": {"type": "array", "items": {
        "type": "object",
        "properties": {
            "on_screen_text": {"type": "string"},
            "post_caption": {"type": "string"},
            "angle": {"type": "string"},
            "inspired_by": {"type": "string"},
            "sound_suggestion": {"type": "string"},
            "track": {"type": "string"},
            "sound_reason": {"type": "string"},
            "virality_score": {"type": "integer"},
            "score_reason": {"type": "string"},
            "positives": {"type": "array", "items": {"type": "string"}},
            "trend": {"type": "string"},
            "source": {"type": "string", "enum": ["instagram", "tiktok", "trends", "original"]},
            "series": {"type": "string"},
            "negatives": {"type": "array", "items": {"type": "string"}},
            "inspirations": {"type": "array", "items": {
                "type": "object", "properties": {"ref": {"type": "string"}, "took": {"type": "string"}},
                "required": ["ref", "took"], "additionalProperties": False}},
            "keywords": {"type": "array", "items": {
                "type": "object", "properties": {"word": {"type": "string"}, "ref": {"type": "string"}, "why": {"type": "string"}},
                "required": ["word", "ref", "why"], "additionalProperties": False}},
        },
        "required": ["on_screen_text", "post_caption", "angle", "inspired_by", "sound_suggestion", "sound_reason",
                     "track", "virality_score", "score_reason", "positives", "negatives", "trend", "source", "series",
                     "inspirations", "keywords"],
        "additionalProperties": False}}},
    "required": ["reels"],
    "additionalProperties": False,
}

PLAN_SYSTEM = """You plan Instagram trial reels for a creator. Each reel = one clip + one line of on-screen text (the hook) + a post caption + sound.

The reel uses only the part of the clip in CLIP reel_cut (the frames are from that part), starting just before its
biggest sound moment. Write for what the viewer sees and hears in that part: never quote timings from the full clip
("13 seconds of calm") or promise a payoff that comes later.

Write about what THIS clip actually shows (see CLIP, and the creator's own description of it if given: it says what
the clip is for, so follow it). The creator's past reels tell you their voice and what works for them; they don't
mean every clip is about the same thing.

Hook rules:
- Under 8 words. The creator's own voice: calm, confident, a little cheeky, quiet-luxury. Plain text, no emoji, no hashtags.
- Build from patterns that are proven to win (the creator's own winners first, then topic and competitor winners). Adapt them; never copy a line word for word, and never reuse one of the creator's past hooks.
- Every reel in a batch must test a clearly different angle (e.g. spec flex, sound, humour, relatable POV, money/value question, identity).
- Learn from results: lean into angles and sounds that won in the creator's own trial reels and away from those that lost, but keep about 1 in 5 reels as a fresh experiment.

Research mix: every reel has a source = the research it is mainly built on. The request gives exact counts per source.
- instagram: a hook, format or sound proven on Instagram right now (the creator's own winners first, then topic
  winners and competitor outliers). The safe bet.
- tiktok: a hook, format or sound that is winning or rising in TIKTOK RESEARCH but isn't big on Instagram yet. The
  early-wave bet. If you suggest a TikTok sound, write it as "Name — Artist (rising on TikTok; use it if it's in
  Instagram's library, otherwise original audio)".
- trends: riskier. Rides current news or a Google trend from TRENDING NOW that genuinely ties to what's in the clip
  (e.g. a new Batman film trending + a black car → "Bruce Wayne spec"); set trend to that trend's name. If not enough
  trends fit naturally, make it a bold experiment instead (an angle the creator has never tried, a polarising opinion,
  a cultural reference) with trend "". A forced trend tie-in looks cringe. Never use tragedies, politics or news about
  real people's misfortune.
- original: the trend-setter bet. Don't adapt anything that already exists. Use the research to spot the WHITE
  SPACE (what nobody in this niche is doing: a format, a point of view, a recurring bit) and make something only this
  creator could post, in their voice, built around their car, style and life. Make it repeatable, so it could become
  a series people recognise as theirs. Set series to a short name for the format (e.g. "Rules of the DB12",
  "One jacket, three ways"). Fit the series to THIS clip's subject. If SERIES TO CONTINUE lists a winning series, at least one
  original reel should be its next part: use that series name exactly and keep the format, with a fresh line.
  inspired_by: say what gap it fills ("none of the top 30 reels for this topic do X") or which of the creator's own reels it builds on.
Only trends reels may have a trend; all others have trend "". Only original reels have a series; all others have series "".
inspired_by must name research from the reel's own source.

post_caption: the text under the reel. It complements the hook instead of repeating it: 1-2 short lines in the
creator's voice that add context or a reason to engage (a question, "save this for later", a detail viewers can't
see), under 150 characters, at most one emoji, then 3-5 specific hashtags for this clip's topic on a new line.
sound_suggestion: the best-fitting trending Instagram sound from the research (name — artist), or "original audio (engine)" when the clip's own sound is the point (start-ups, revs). Most winning car reels use original audio.
sound_reason: one line on why this sound (cite the research, e.g. "9 of the top 12 reels for this topic use their own sound").
track: a filename from the creator's own music library that fits the mood, or "" to keep the clip's own sound. Only use a library track when the clip's sound isn't the point.

virality_score (0–100): your honest prediction of how this reel will do *for this creator*, relative to their normal trial reels (50 = typical, 80+ = likely a top-10% reel). Base it on: how well similar reels (topic and competitor) did, how the creator's past reels with this angle or sound did, the strength of the hook, and the clip's moment. score_reason: one line naming the main evidence.
positives: 2–4 short reasons it could do well, each citing real evidence from the research or the creator's results (numbers where you have them).
negatives: 1–3 short honest risks that could hold it back (e.g. "no text hooks in the top reels for this topic", "similar line flopped for you at 3.1K").
inspired_by: name the exact source — the winning reel(s) or pattern this hook adapts, with account and views, e.g. "@itisbainz 'POV: …' 412K (5.2x his median)" or "your own 'Sunday spec' reel, 61K".

Every research item in the request has an id in square brackets, e.g. [I3] (Instagram reel), [T2] (TikTok), [C1]
(competitor outlier), [S4] (a reel the creator saved), [M2] (the creator's own reel), [G5] (Google trending search),
[K7] (what people search on Google/YouTube about this clip's topic).
inspirations: 1–3 research items this reel really borrows from (hook wording, format, structure, sound, pacing).
  ref = the id exactly as written, e.g. "I3". took = what you took from it in a few words ("the 'POV:' opener",
  "the night walk-up format", "this sound"). Original reels may cite the items whose gap they fill. Only cite ids that
  exist in the request; if nothing was borrowed, return [].
keywords: words or phrases in on_screen_text or post_caption that you chose because of the research: a search people
  make [K..], a trending search [G..], or a phrase that keeps winning on creators' reels [I../T../C..]. word = the word
  or phrase as written in the reel, ref = the id, why = a few words ("people search 'db12 sound'", "trending on Google").
  Only real, cited reasons: [] is fine."""


def plan_reels(frames, clip_info, n, context, library, sources=None, remake=None):
    text = f"""CLIP: {json.dumps(clip_info, ensure_ascii=False)}

{context}

MY MUSIC LIBRARY (filenames for `track`): {", ".join(library) or "(empty — use \"\")"}

Plan {n} different reels for this clip. Research mix for this batch (source → number of reels): {json.dumps(sources or {"instagram": n})}"""
    if remake:
        text += f"""

REMAKE: this is a new version of a reel that is already posted. Apply the lesson below. Keep what worked, change what
didn't. The hook must be clearly new (a new line, not a reword), so Instagram doesn't treat it as a duplicate.
{json.dumps(remake, ensure_ascii=False)}"""
    return _ask([*_images(frames), {"type": "text", "text": text}], PLAN_SCHEMA,
                system=PLAN_SYSTEM, effort="medium")["reels"][:n]


SPOT_SCHEMA = {
    "type": "object",
    "properties": {"spot": {"type": "integer"}, "reason": {"type": "string"}},
    "required": ["spot", "reason"],
    "additionalProperties": False,
}


def choose_text_spot(preview_jpg, n_spots, text, examples="", subject=""):
    """Look at the numbered candidate boxes on 3 moments of the reel and pick where the text should go."""
    shows = f"\nThe clip shows: {subject}\n" if subject else ""
    prompt = f"""This picture shows 3 moments (left to right) from a vertical Instagram reel. The yellow boxes numbered 1–{n_spots}
(top to bottom) are candidate places for one line of small, thin white, centred on-screen text: "{text}".
The low numbers sit near the top of the frame and the high numbers near the bottom: the text goes either near the top
or near the bottom, whichever suits this clip, never across the middle.
{shows}
Pick the box where the text will be easiest to read AND blocks nothing important, in all 3 moments:
1. Readability first: the background must be dark or mid-toned and even. Never pick bright or overexposed areas
   (windscreen, sky, white walls, glare, bright windows) — thin white text disappears there.
2. Don't cover the steering wheel, dashboard screens, badges or logos, faces, hands or wrists (watch, rings), or the
   main action. Covering calm, dark parts of the scene is fine: the centre console, legs, seats, floor, dark trim.
   In outfit or fashion clips the clothes are the point: don't cover the garment being shown.
3. People move between and during these moments: never pick a box that touches or nearly touches a head, face, hand or
   phone in ANY of the 3 moments. Leave a clear gap. If every box touches someone at some moment (e.g. they walk
   towards the camera), pick the one that stays clear longest, above all in the first moment: the hook is read first.
4. If several are equally good, prefer the bottom group.
{examples}
spot: the box number. reason: one short line saying what's behind the text and what it keeps clear, e.g.
"over the dark centre console — easy to read and keeps the wheel and screen clear"."""
    return _ask([*_images([preview_jpg]), {"type": "text", "text": prompt}], SPOT_SCHEMA, effort="low", max_tokens=2000)


EDIT_SCHEMA = {
    "type": "object",
    "properties": {
        "on_screen_text": {"type": "string"},
        "post_caption": {"type": "string"},
        "look": {"type": "string", "enum": ["keep", "match", "natural", "moody", "none", "warm", "cool", "punchy", "film", "mono"]},
        "adjust": {"type": "object", "properties": {
            "brightness": {"type": "integer"}, "contrast": {"type": "integer"},
            "saturation": {"type": "integer"}, "warmth": {"type": "integer"}},
            "required": ["brightness", "contrast", "saturation", "warmth"], "additionalProperties": False},
        "text_position": {"type": "string", "enum": ["keep", "top", "bottom"]},
        "text_layout": {"type": "string", "enum": ["keep", "one_line", "auto", "split"]},
        "lines": {"type": "array", "items": {"type": "string"}},
        "text_size": {"type": "string", "enum": ["keep", "smaller", "bigger", "reset"]},
        "start_seconds": {"type": ["number", "null"]},
        "length_seconds": {"type": ["number", "null"]},
        "reply": {"type": "string"},
    },
    "required": ["on_screen_text", "post_caption", "look", "adjust", "text_position", "text_layout", "lines",
                 "text_size", "start_seconds", "length_seconds", "reply"],
    "additionalProperties": False,
}


def edit_reel(current, message, history):
    """Turn the creator's request ("darker and warmer, text at the top") into concrete edits."""
    past = "\n".join(f"- them: {h['you']}\n  you: {h['bot']}" for h in history) or "(none)"
    text = f"""You edit one Instagram reel for a creator. Current settings:
{json.dumps(current, ensure_ascii=False)}

Earlier requests on this reel:
{past}

Their new request: "{message}"

Return the settings AFTER the change:
- on_screen_text / post_caption: the new wording if they asked to change it, otherwise "" (keep).
- look: "keep", or a colour look: "match" (copies their own reels), "natural" (real colour, slightly dark),
  "moody" (desaturated, vignette), "none" (as filmed), or a filter: "warm", "cool", "punchy" (more contrast and
  colour), "film" (soft, faded), "mono" (black and white).
- adjust: the FULL new values from -100 to 100 for brightness, contrast, saturation and warmth (0 = unchanged).
  Start from the current adjust values. "A bit" ≈ 15, "more"/normal ≈ 25-35, "a lot" ≈ 50. "Washed out" means more
  contrast and saturation and a little less brightness. Never change values they didn't ask about.
- text_position: "top", "bottom" or "keep".
- text_layout: "one_line" (all on one line), "auto" (wrap long lines automatically), "split" (their own line breaks:
  put each line in `lines`, e.g. ["Door shut.", "World on mute."]) or "keep". `lines` is [] unless split.
  The words in `lines` must be the on-screen text (new wording if they changed it), just broken into lines.
- text_size: "smaller", "bigger", "reset" (normal size) or "keep".
- start_seconds: a new start point in the clip if they asked to use a different moment, otherwise null.
- length_seconds: the new reel length in seconds if they asked for it longer/shorter or "the whole clip"
  (use the clip's full length for that), otherwise null. "A bit longer" ≈ +3s. Max 180.
- reply: one short friendly line saying what you changed (or what you can't do)."""
    return _ask([{"type": "text", "text": text}], EDIT_SCHEMA, effort="low", max_tokens=3000)


LESSON_SCHEMA = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": ["winner", "ok", "flop"]},
        "headline": {"type": "string"},
        "worked": {"type": "array", "items": {"type": "string"}},
        "didnt": {"type": "array", "items": {"type": "string"}},
        "tweak": {"type": "string"},
        "change": {"type": "array", "items": {"type": "string", "enum": ["hook", "opening", "length", "part", "sound", "text_look", "colour", "caption"]}},
        "new_start": {"type": "number"},
        "new_length": {"type": "number"},
        "lesson_for_next": {"type": "string"},
    },
    "required": ["verdict", "headline", "worked", "didnt", "tweak", "change", "new_start", "new_length", "lesson_for_next"],
    "additionalProperties": False,
}


def review_result(reel, results, usual, clip_seconds, others=""):
    """After a trial reel has results: what worked, what didn't, and one tweak worth testing in a remake."""
    text = f"""You review how an Instagram TRIAL reel did (shown to non-followers only), so the creator learns and the next version does better.

THE REEL: {json.dumps(reel, ensure_ascii=False)}
The clip it came from is {clip_seconds:.1f}s long; the reel used {reel.get("start", 0):.1f}s–{reel.get("start", 0) + reel.get("seconds", 0):.1f}s.

RESULTS (hours after posting → numbers): {json.dumps(results)}
The creator's usual views per reel: {usual:,}.
{others}

How to read it: views vs usual is the headline. Shares and saves per 1,000 views show whether people valued it.
Average watch time vs reel length shows whether the opening held people (a short watch on a long reel = the hook or
first second lost them). Likes per view show whether the payoff landed. Be specific and honest; numbers beat adjectives.

- verdict: winner (clearly above usual, or strong shares/saves), ok, or flop (clearly below usual).
- headline: one plain sentence a 10-year-old would get, e.g. "Half your usual views: people scrolled past in the first second."
- worked / didnt: 1–3 short points each, citing the numbers.
- tweak: the ONE change most likely to do better in a remake of this same clip, in plain words.
- change: which parts the remake should change.
- new_start, new_length: the part of the clip the remake should use, in seconds of the clip (keep the current ones if the part isn't the problem).
  For a winner, pick a different part of the clip so the remake isn't a duplicate.
- lesson_for_next: one line ReelBot should remember for every future reel (e.g. "Night walk-ups beat daytime 3 to 1")."""
    return _ask([{"type": "text", "text": text}], LESSON_SCHEMA, effort="medium", max_tokens=6000)
