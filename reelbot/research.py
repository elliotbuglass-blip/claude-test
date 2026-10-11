"""Turns your stats + competitor outliers into a research brief: what on-screen hooks win, and why.

Writes data/research_brief.json (read by the caption writer) and output/picklist.md (for you).
"""

import json
from datetime import date

import anthropic

from . import competitors, stats
from .settings import DATA, OUTPUT

MODEL = "claude-opus-5-5"
BRIEF = DATA / "research_brief.json"

SCHEMA = {
    "type": "object",
    "properties": {
        "winning_patterns": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string"},
                    "why_it_works": {"type": "string"},
                    "examples": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["pattern", "why_it_works", "examples"],
                "additionalProperties": False,
            },
        },
        "avoid": {"type": "array", "items": {"type": "string"}},
        "outlier_reads": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "code": {"type": "string"},
                    "why_it_won": {"type": "string"},
                    "fits_me": {"type": "boolean"},
                    "fit_reason": {"type": "string"},
                },
                "required": ["code", "why_it_won", "fits_me", "fit_reason"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["winning_patterns", "avoid", "outlier_reads"],
    "additionalProperties": False,
}

PROMPT = """You are analysing short-form video hooks for this account: {niche}

The format: a short, moody clip with ONE line of text burned onto the video. That on-screen text is the hook. It decides whether people keep watching. Below is the ON-SCREEN TEXT (not the post caption) of reels, with their results.

{data}

Do three things:
1. winning_patterns: 4-8 specific hook patterns that explain the winners (e.g. "spec identity flex: '<colour> spec… always'"). Quote real examples. Explain the mechanism in one line: why does it stop the scroll for this audience?
2. avoid: patterns that clearly underperform, with a short example each.
3. outlier_reads: for EVERY competitor outlier (by code), say why it beat that creator's normal views, and whether the hook would fit this account's content (cars, menswear, fashion; filmed by them, moody), with a one-line reason.

Be concrete. Wording differences matter: the same idea phrased two ways can differ 35x in views."""


def _fmt_mine(r):
    skip = r.get("media_reel_skip_rate")
    return (f'- "{stats.hook(r)}" | {r.get("media_views", 0):,} views'
            f'{f" | skip {skip:.0%}" if isinstance(skip, (int, float)) else ""}'
            f'{f" | shows: {r["visual"]}" if r.get("visual") else ""}')


def build(niche):
    mine = stats.load()
    top, bottom = stats.winners_and_losers(mine, 15)
    outliers = competitors.load()
    sections = ["MY TOP REELS:\n" + "\n".join(_fmt_mine(r) for r in top),
                "MY WORST REELS:\n" + "\n".join(_fmt_mine(r) for r in bottom)]
    if outliers:
        sections.append("COMPETITOR OUTLIERS (views vs that creator's median):\n" + "\n".join(
            f'- code {o["code"]} @{o["account"]}: on-screen "{o.get("on_screen_text") or "(none)"}"'
            f' | {o["views"]:,} views = {o["ratio"]}x their median'
            f' | shows: {o.get("visual") or "?"} | post caption: "{o["post_caption"][:100]}"'
            for o in outliers))

    client = anthropic.Anthropic()
    with client.beta.messages.stream(
        model=MODEL,
        max_tokens=32000,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        output_config={"effort": "high", "format": {"type": "json_schema", "schema": SCHEMA}},
        messages=[{"role": "user", "content": PROMPT.format(niche=niche, data="\n\n".join(sections))}],
    ) as stream:
        response = stream.get_final_message()
    if response.stop_reason == "refusal":
        raise RuntimeError("Claude declined to write the research brief.")
    brief = json.loads(next(b.text for b in response.content if b.type == "text"))
    brief["date"] = date.today().isoformat()
    DATA.mkdir(exist_ok=True)
    BRIEF.write_text(json.dumps(brief, ensure_ascii=False, indent=1))
    _write_picklist(brief, outliers)
    return brief


def load():
    return json.loads(BRIEF.read_text()) if BRIEF.exists() else None


def _write_picklist(brief, outliers):
    reads = {r["code"]: r for r in brief["outlier_reads"]}
    lines = [f"# Radar pick list - {brief['date']}", "",
             "| # | Ratio | Views | Creator | On-screen hook | Fits? | Link |",
             "|---|-------|-------|---------|----------------|-------|------|"]
    for i, o in enumerate(outliers, 1):
        fit = "yes" if reads.get(o["code"], {}).get("fits_me") else "no"
        hook = (o.get("on_screen_text") or "(no text)").replace("|", "/")
        lines.append(f"| {i} | {o['ratio']}x | {o['views']:,} | @{o['account']} | {hook} | {fit} | {o['url']} |")
    lines += ["", "## Winning patterns", ""]
    for p in brief["winning_patterns"]:
        lines.append(f"- **{p['pattern']}**: {p['why_it_works']} (e.g. {'; '.join(p['examples'][:3])})")
    lines += ["", "## Avoid", ""] + [f"- {a}" for a in brief["avoid"]]
    lines += ["", "## Why each outlier won", ""]
    for o in outliers:
        r = reads.get(o["code"])
        if r:
            lines.append(f"- **@{o['account']}** “{o.get('on_screen_text') or ''}”: {r['why_it_won']}"
                         f" Fits you: {'yes' if r['fits_me'] else 'no'}, {r['fit_reason']}")
    OUTPUT.mkdir(exist_ok=True)
    (OUTPUT / "picklist.md").write_text("\n".join(lines) + "\n")
