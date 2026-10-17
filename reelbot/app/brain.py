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


def analyse_clip(frames, duration, has_audio, loud_moment, niche):
    """Work out what a clip shows, and whether it can stand alone (main) or is a cut-in (b-roll)."""
    text = f"""These are frames (in time order) from one raw clip for an Instagram creator: {niche}

Clip facts: {duration:.1f}s long, {"has sound" if has_audio else "no sound"}, loudest moment around {loud_moment:.1f}s.

- kind: "main" if it can carry a reel on its own (a walk-up, start-up, drive, POV, reveal with a clear moment).
  "broll" if it's a short detail or filler shot (door handle, badge, sill plate, interior detail) that only works cut into another clip.
- kind_reason: one short line.
- subject: what it shows, e.g. "black Aston Martin DB12, start-up from the driver's seat, overcast day".
- hashtags: 3–5 Instagram hashtags (no #) to research what similar reels are doing, specific to general,
  e.g. ["astonmartindb12", "db12", "astonmartin", "supercar"].
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
            "virality_score": {"type": "integer"},
            "score_reason": {"type": "string"},
        },
        "required": ["on_screen_text", "post_caption", "angle", "inspired_by", "sound_suggestion",
                     "track", "virality_score", "score_reason"],
        "additionalProperties": False}}},
    "required": ["reels"],
    "additionalProperties": False,
}

PLAN_SYSTEM = """You plan Instagram trial reels for a creator. Each reel = one clip + one line of on-screen text (the hook) + a post caption + sound.

Hook rules:
- Under 8 words. The creator's own voice: calm, confident, a little cheeky, quiet-luxury. Plain text, no emoji, no hashtags.
- Build from patterns that are proven to win (the creator's own winners first, then topic and competitor winners). Adapt them; never copy a line word for word, and never reuse one of the creator's past hooks.
- Every reel in a batch must test a clearly different angle (e.g. spec flex, sound, humour, relatable POV, money/value question, identity).
- Learn from results: lean into angles and sounds that won in the creator's own trial reels and away from those that lost, but keep about 1 in 5 reels as a fresh experiment.

post_caption: usually the hook or a close variant, one emoji allowed.
sound_suggestion: the best-fitting trending Instagram sound from the research (name — artist), or "original audio (engine)" when the clip's own sound is the point (start-ups, revs). Most winning car reels use original audio.
track: a filename from the creator's own music library that fits the mood, or "" to keep the clip's own sound. Only use a library track when the clip's sound isn't the point.

virality_score (0–100): your honest prediction of how this reel will do *for this creator*, relative to their normal trial reels (50 = typical, 80+ = likely a top-10% reel). Base it on: how well similar reels (topic and competitor) did, how the creator's past reels with this angle or sound did, the strength of the hook, and the clip's moment. score_reason: one line naming the main evidence."""


def plan_reels(frames, clip_info, n, context, library):
    text = f"""CLIP: {json.dumps(clip_info, ensure_ascii=False)}

{context}

MY MUSIC LIBRARY (filenames for `track`): {", ".join(library) or "(empty — use \"\")"}

Plan {n} different reels for this clip."""
    return _ask([*_images(frames), {"type": "text", "text": text}], PLAN_SCHEMA,
                system=PLAN_SYSTEM, effort="medium")["reels"][:n]
