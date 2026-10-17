"""ReelBot's brain: Claude looks at clips, decides main vs b-roll, and plans reels with a virality score."""

import base64
import json

import anthropic

MODEL = "claude-opus-5-5"


def _images(frames):
    return [{"type": "image", "source": {"type": "base64", "media_type": "image/jpeg",
                                         "data": base64.standard_b64encode(f).decode()}} for f in frames]


def _ask(content, schema, system=None, effort="medium", max_tokens=16000):
    client = anthropic.Anthropic()
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
    },
    "required": ["kind", "kind_reason", "subject", "hashtags", "mood", "highlight"],
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
- highlight: the best moment in one line (e.g. "engine fires up at ~10s")."""
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
- relevant: true only if the reel is genuinely about the same kind of thing as: {subject}. (Hashtags attract junk like house listings.)"""})
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
        },
        "required": ["on_screen_text", "post_caption", "angle", "inspired_by", "sound_suggestion", "sound_reason",
                     "track", "virality_score", "score_reason", "positives", "negatives", "trend", "source", "series"],
        "additionalProperties": False}}},
    "required": ["reels"],
    "additionalProperties": False,
}

PLAN_SYSTEM = """You plan Instagram trial reels for a creator. Each reel = one clip + one line of on-screen text (the hook) + a post caption + sound.

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

post_caption: usually the hook or a close variant, one emoji allowed.
sound_suggestion: the best-fitting trending Instagram sound from the research (name — artist), or "original audio (engine)" when the clip's own sound is the point (start-ups, revs). Most winning car reels use original audio.
sound_reason: one line on why this sound (cite the research, e.g. "9 of the top 12 reels for this topic use their own sound").
track: a filename from the creator's own music library that fits the mood, or "" to keep the clip's own sound. Only use a library track when the clip's sound isn't the point.

virality_score (0–100): your honest prediction of how this reel will do *for this creator*, relative to their normal trial reels (50 = typical, 80+ = likely a top-10% reel). Base it on: how well similar reels (topic and competitor) did, how the creator's past reels with this angle or sound did, the strength of the hook, and the clip's moment. score_reason: one line naming the main evidence.
positives: 2–4 short reasons it could do well, each citing real evidence from the research or the creator's results (numbers where you have them).
negatives: 1–3 short honest risks that could hold it back (e.g. "no text hooks in the top reels for this topic", "similar line flopped for you at 3.1K").
inspired_by: name the exact source — the winning reel(s) or pattern this hook adapts, with account and views, e.g. "@itisbainz 'POV: …' 412K (5.2x his median)" or "your own 'Sunday spec' reel, 61K"."""


def plan_reels(frames, clip_info, n, context, library, sources=None):
    text = f"""CLIP: {json.dumps(clip_info, ensure_ascii=False)}

{context}

MY MUSIC LIBRARY (filenames for `track`): {", ".join(library) or "(empty — use \"\")"}

Plan {n} different reels for this clip. Research mix for this batch (source → number of reels): {json.dumps(sources or {"instagram": n})}"""
    return _ask([*_images(frames), {"type": "text", "text": text}], PLAN_SCHEMA,
                system=PLAN_SYSTEM, effort="medium")["reels"][:n]


SPOT_SCHEMA = {
    "type": "object",
    "properties": {"spot": {"type": "integer"}, "reason": {"type": "string"}},
    "required": ["spot", "reason"],
    "additionalProperties": False,
}


def choose_text_spot(preview_jpg, n_spots, text, examples=""):
    """Look at the numbered candidate boxes on 3 moments of the reel and pick where the text should go."""
    prompt = f"""This picture shows 3 moments (left to right) from a vertical Instagram reel. The yellow boxes numbered 1–{n_spots}
(top to bottom) are candidate places for one line of small, thin white on-screen text: "{text}".

Pick the box where the text will be easiest to read AND blocks nothing important, in all 3 moments:
1. Readability first: the background must be dark or mid-toned and even. Never pick bright or overexposed areas
   (windscreen, sky, white walls, glare, bright windows) — thin white text disappears there.
2. Don't cover the steering wheel, dashboard screens, badges or logos, faces, or the main action.
   Covering calm, dark parts of the scene is fine: the centre console, an arm or legs, seats, floor, dark trim.
3. If several are equally good, prefer the lower-middle of the frame.
{examples}
spot: the box number. reason: one short line saying what's behind the text and what it keeps clear, e.g.
"over the dark centre console — easy to read and keeps the wheel and screen clear"."""
    return _ask([*_images([preview_jpg]), {"type": "text", "text": prompt}], SPOT_SCHEMA, effort="low", max_tokens=2000)
