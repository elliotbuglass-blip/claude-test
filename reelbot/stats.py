"""Pulls your own reel results from Windsor.ai and summarises what worked."""

import json
import statistics
from datetime import datetime, timezone

import requests

from . import vision
from .settings import DATA, env

FIELDS = [
    "timestamp", "media_id", "media_caption", "media_permalink", "media_url",
    "media_thumbnail_url", "media_views", "media_reach", "media_reel_avg_watch_time",
    "media_reel_skip_rate", "media_shares", "media_saved", "media_like_count",
]
MY_REELS = DATA / "my_reels.json"
SNAPSHOTS = DATA / "snapshots.jsonl"


def refresh(date_preset="last_30d"):
    """Download fresh stats into data/my_reels.json and log a snapshot of every reel."""
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

    # One line per reel per run: lets you see whether a trial reel is still climbing.
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with SNAPSHOTS.open("a") as f:
        for r in rows:
            f.write(json.dumps({"checked_at": now, "media_id": r.get("media_id"),
                                "views": r.get("media_views"), "skip_rate": r.get("media_reel_skip_rate"),
                                "shares": r.get("media_shares"), "saved": r.get("media_saved")}) + "\n")
    return rows


def load():
    if not MY_REELS.exists():
        return []
    rows = json.loads(MY_REELS.read_text())
    texts = vision._cache()
    for r in rows:
        seen = texts.get(f"me:{r.get('media_id')}")
        if seen:
            r["on_screen_text"] = seen["on_screen_text"]
            r["visual"] = seen["visual"]
    return rows


def read_onscreen_text():
    """Have Claude read the burned-in text on each of your reels (cached, so only new ones cost)."""
    rows = load()
    items = [{"key": f"me:{r['media_id']}", "video": r.get("media_url"),
              "thumbnail": r.get("media_thumbnail_url")}
             for r in rows if r.get("media_id")]
    vision.read_reels(items)
    return load()


def hook(r):
    """The on-screen hook if we've read it, otherwise the post caption (marked as such)."""
    if r.get("on_screen_text"):
        return r["on_screen_text"]
    caption = (r.get("media_caption") or "").split("\n")[0]
    return f"{caption} [post caption — on-screen text not read yet]"


def winners_and_losers(rows, n=12):
    """Top and bottom reels by views, so the caption writer can copy what works."""
    ranked = sorted(rows, key=lambda r: r.get("media_views") or 0, reverse=True)
    return ranked[:n], ranked[-n:]


def summary(rows):
    if not rows:
        return "No stats yet. Run: python -m reelbot stats --refresh"
    views = [r.get("media_views") or 0 for r in rows]
    top, bottom = winners_and_losers(rows, 10)
    read = sum(1 for r in rows if r.get("on_screen_text") is not None)
    lines = [
        f"{len(rows)} reels | median views {int(statistics.median(views)):,} | best {max(views):,}"
        f" | on-screen text read for {read}/{len(rows)}",
        "",
        "TOP 10 (copy these vibes):",
    ]
    lines += [_row(r) for r in top]
    lines += ["", "BOTTOM 10 (avoid these vibes):"]
    lines += [_row(r) for r in bottom]
    return "\n".join(lines)


def _row(r):
    skip = r.get("media_reel_skip_rate")
    skip_txt = f"skip {skip:.0%}" if isinstance(skip, (int, float)) else ""
    return f"  {r.get('media_views', 0):>10,}  {skip_txt:>9}  {hook(r)}"
