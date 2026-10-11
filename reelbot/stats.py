"""Pulls your own reel results from Windsor.ai and summarises what worked."""

import json
import statistics

import requests

from .settings import DATA, env

FIELDS = [
    "timestamp", "media_id", "media_caption", "media_permalink", "media_views",
    "media_reach", "media_reel_avg_watch_time", "media_reel_skip_rate",
    "media_shares", "media_saved", "media_like_count",
]
MY_REELS = DATA / "my_reels.json"


def refresh(date_preset="last_30d"):
    """Download fresh stats into data/my_reels.json."""
    resp = requests.get(
        "https://connectors.windsor.ai/instagram",
        params={
            "api_key": env("WINDSOR_API_KEY"),
            "date_preset": date_preset,
            "fields": ",".join(FIELDS),
        },
        timeout=300,
    )
    resp.raise_for_status()
    rows = [r for r in resp.json().get("data", []) if r.get("media_views") is not None]
    DATA.mkdir(exist_ok=True)
    MY_REELS.write_text(json.dumps(rows, ensure_ascii=False, indent=1))
    return rows


def load():
    if not MY_REELS.exists():
        return []
    return json.loads(MY_REELS.read_text())


def winners_and_losers(rows, n=12):
    """Top and bottom reels by views, so the caption writer can copy what works."""
    ranked = sorted(rows, key=lambda r: r.get("media_views") or 0, reverse=True)
    return ranked[:n], ranked[-n:]


def summary(rows):
    if not rows:
        return "No stats yet. Run: python -m reelbot stats"
    views = [r.get("media_views") or 0 for r in rows]
    top, bottom = winners_and_losers(rows, 10)
    lines = [
        f"{len(rows)} reels | median views {int(statistics.median(views)):,} | best {max(views):,}",
        "",
        "TOP 10 (copy these vibes):",
    ]
    for r in top:
        lines.append(_row(r))
    lines += ["", "BOTTOM 10 (avoid these vibes):"]
    for r in bottom:
        lines.append(_row(r))
    return "\n".join(lines)


def _row(r):
    skip = r.get("media_reel_skip_rate")
    skip_txt = f"skip {skip:.0%}" if isinstance(skip, (int, float)) else ""
    caption = (r.get("media_caption") or "").split("\n")[0]
    return f"  {r.get('media_views', 0):>10,}  {skip_txt:>9}  {caption}"
