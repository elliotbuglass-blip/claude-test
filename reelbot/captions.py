"""Asks Claude to write the on-screen hook text, based on the research brief and real on-screen hooks."""

import base64
import json

import anthropic

from . import competitors, research, stats

MODEL = "claude-opus-5-5"

SCHEMA = {
    "type": "object",
    "properties": {
        "captions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "on_screen_text": {"type": "string"},
                    "post_caption": {"type": "string"},
                    "angle": {"type": "string"},
                    "inspired_by": {"type": "string"},
                },
                "required": ["on_screen_text", "post_caption", "angle", "inspired_by"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["captions"],
    "additionalProperties": False,
}

SYSTEM = """You write the text burned onto Instagram trial reels.

The account: {niche}

The format: a short, moody clip with one line of text on screen. That on-screen text is the hook. It decides whether someone keeps watching or skips in the first 3 seconds.

Rules for on_screen_text:
- Build every hook from a winning pattern in the research brief, or from a real on-screen hook that won (theirs or a competitor outlier marked as fitting). Adapt the structure to THIS clip; never copy a competitor's line word for word.
- Under 8 words. Natural, confident, a bit cheeky. How a real person types, not an ad.
- Plain text only: NO emoji and no hashtags (emoji can't be rendered onto the video). An ellipsis (…) or a question mark is fine.
- Each caption must use a clearly different pattern/angle, so the trial reels genuinely test different ideas.
- Never reuse one of the account's previous hooks word for word.

post_caption: the text under the post. Usually the same line as the hook or a close variant; one emoji is fine here.
angle: the pattern used, in 2-4 words. inspired_by: which winning example it adapts (quote it)."""


def _frame_block(frame_path):
    data = base64.standard_b64encode(frame_path.read_bytes()).decode()
    return {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": data}}


def _research_text():
    rows = stats.load()
    top, bottom = stats.winners_and_losers(rows)
    fmt = lambda r: f'- "{stats.hook(r)}" → {r.get("media_views", 0):,} views, skip rate {r.get("media_reel_skip_rate", "?")}'
    parts = []
    brief = research.load()
    if brief:
        parts.append("RESEARCH BRIEF — WINNING HOOK PATTERNS:\n" + "\n".join(
            f'- {p["pattern"]}: {p["why_it_works"]} e.g. {" | ".join(p["examples"][:3])}'
            for p in brief["winning_patterns"]))
        parts.append("AVOID:\n" + "\n".join(f"- {a}" for a in brief["avoid"]))
        fits = {r["code"] for r in brief["outlier_reads"] if r["fits_me"]}
        outliers = [o for o in competitors.load() if o["code"] in fits and o.get("on_screen_text")]
        if outliers:
            parts.append("COMPETITOR OUTLIER HOOKS THAT FIT THIS ACCOUNT (on-screen text):\n" + "\n".join(
                f'- @{o["account"]}: "{o["on_screen_text"]}" → {o["ratio"]}x their normal views ({o.get("visual") or ""})'
                for o in outliers[:20]))
    parts.append("MY BEST REELS (on-screen hook):\n" + "\n".join(fmt(r) for r in top))
    parts.append("MY WORST REELS (on-screen hook):\n" + "\n".join(fmt(r) for r in bottom))
    already = sorted({stats.hook(r) for r in rows})
    parts.append("ALREADY USED (don't repeat):\n" + "\n".join(already))
    return "\n\n".join(parts)


def write_captions(niche, frame_path, clip_notes, count):
    client = anthropic.Anthropic()
    user_content = [
        _frame_block(frame_path),
        {"type": "text", "text": (
            f"{_research_text()}\n\n"
            f"THIS CLIP: the image above is a frame from it. Notes: {clip_notes or 'none'}\n\n"
            f"Write {count} on-screen hooks for this clip."
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
