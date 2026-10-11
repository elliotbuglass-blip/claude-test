"""Asks Claude to write on-screen captions based on what has worked for you and your niche."""

import base64
import json

import anthropic

from . import competitors, stats

MODEL = "claude-opus-5-5"

SCHEMA = {
    "type": "object",
    "properties": {
        "captions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "angle": {"type": "string"},
                },
                "required": ["text", "angle"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["captions"],
    "additionalProperties": False,
}

SYSTEM = """You write the short on-screen text for Instagram trial reels.

The account: {niche}

How these reels work: a short, moody clip with one line of text on screen. The text is the hook. It decides whether someone keeps watching or skips in the first 3 seconds.

Rules:
- Base every caption on patterns from the account's own winners and the competitor posts provided. Lean into what got the most views and the lowest skip rate; steer away from what flopped.
- Keep each one under 8 words. Natural, confident, a bit cheeky. Write how a real person types, not like an ad.
- An ellipsis (…), a question, or one emoji is fine where it suits. No hashtags in the on-screen text.
- Every caption must take a clearly different angle (identity/spec flex, relatable question, pop-culture reference, sound/sensation, "dupe"/value take, etc.) so the trial reels genuinely test different ideas.
- Never repeat a caption that has already been posted word for word.
- Describe the angle in 2-4 words."""


def _frame_block(frame_path):
    data = base64.standard_b64encode(frame_path.read_bytes()).decode()
    return {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": data}}


def _research_text():
    rows = stats.load()
    top, bottom = stats.winners_and_losers(rows)
    fmt = lambda r: f'- "{(r.get("media_caption") or "").splitlines()[0]}" → {r.get("media_views", 0):,} views, skip rate {r.get("media_reel_skip_rate", "?")}'
    parts = [
        "MY BEST REELS:\n" + "\n".join(fmt(r) for r in top),
        "MY WORST REELS:\n" + "\n".join(fmt(r) for r in bottom),
    ]
    comp = competitors.top_posts()
    if comp:
        parts.append(
            "TOP COMPETITOR REELS (likes per 1k followers):\n"
            + "\n".join(f'- @{p["account"]}: "{p["caption"][:120]}" → {p["likes_per_1k_followers"]}' for p in comp)
        )
    already = sorted({(r.get("media_caption") or "").splitlines()[0] for r in rows})
    parts.append("ALREADY POSTED (don't repeat):\n" + "\n".join(already))
    return "\n\n".join(parts)


def write_captions(niche, frame_path, clip_notes, count):
    client = anthropic.Anthropic()
    user_content = [
        _frame_block(frame_path),
        {"type": "text", "text": (
            f"{_research_text()}\n\n"
            f"THIS CLIP: the image above is a frame from it. Notes: {clip_notes or 'none'}\n\n"
            f"Write {count} on-screen captions for this clip."
        )},
    ]
    response = client.beta.messages.create(
        model=MODEL,
        max_tokens=16000,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        output_config={"effort": "medium", "format": {"type": "json_schema", "schema": SCHEMA}},
        system=SYSTEM.format(niche=niche),
        messages=[{"role": "user", "content": user_content}],
    )
    if response.stop_reason == "refusal":
        raise RuntimeError("Claude declined to write captions for this clip.")
    text = next(b.text for b in response.content if b.type == "text")
    return json.loads(text)["captions"][:count]
