"""Competitor Radar: finds reels that beat their own creator's normal views, then reads their on-screen text.

Gets public reel data from Apify (default, pay-as-you-go, free monthly credit) or HikerAPI
(set radar.source in config.yaml). No login with your own account. Raw pulls are cached in
data/hiker/ so re-scoring never re-spends credits.
"""

import json
import statistics
import time
from datetime import datetime

import requests

from . import vision
from .settings import DATA, env

HIKER = "https://api.hikerapi.com"
RAW_DIR = DATA / "hiker"
OUTLIERS = DATA / "competitors.json"


def _get(path, params):
    # The key is either an env var, or added to every request by a Claude Code network secret
    # (custom header x-access-key on api.hikerapi.com) — then it's blank here.
    key = env("HIKER_API_KEY", required=False)
    for attempt in range(3):
        resp = requests.get(f"{HIKER}{path}", params=params,
                            headers={"x-access-key": key} if key else {}, timeout=60)
        if resp.status_code in (401, 403):
            raise SystemExit("HikerAPI rejected the key (401/403). Check the HikerAPI secret's "
                             "header name is x-access-key, with no prefix.")
        if resp.status_code == 404:
            return None
        if resp.status_code >= 500 and attempt < 2:
            time.sleep(2 * (attempt + 1))
            continue
        resp.raise_for_status()
        return resp.json()


def _first_url(item, key):
    versions = item.get(key) or []
    if isinstance(versions, dict):  # image_versions2 = {"candidates": [...]}
        versions = versions.get("candidates") or []
    return versions[0].get("url") if versions else None


def _normalize(clip):
    if not (clip.get("media_type") == 2 or clip.get("product_type") == "clips"):
        return None
    code = clip.get("code")
    return {
        "code": code,
        "url": f"https://www.instagram.com/reel/{code}/",
        "views": clip.get("play_count") or clip.get("view_count") or 0,
        "likes": clip.get("like_count") or 0,
        "comments": clip.get("comment_count") or 0,
        "taken_at": clip.get("taken_at") or 0,
        "post_caption": (clip.get("caption_text") or "")[:300],
        "video": clip.get("video_url") or _first_url(clip, "video_versions"),
        "thumbnail": clip.get("thumbnail_url") or _first_url(clip, "image_versions2"),
    }


def fetch_account(username, want):
    user = _get("/v1/user/by/username", {"username": username})
    if not user:
        print(f"  ! @{username} not found")
        return None
    reels, cursor = [], None
    while len(reels) < want:
        params = {"user_id": user["pk"]}
        if cursor:
            params["end_cursor"] = cursor
        page = _get("/v1/user/clips/chunk", params)
        if not page:
            break
        clips, cursor = page[0], page[1]
        reels += [r for r in (_normalize(c) for c in clips) if r]
        if not cursor or not clips:
            break
    reels.sort(key=lambda r: r["taken_at"], reverse=True)  # pinned reels come first in the feed
    data = {"username": username, "followers": user.get("follower_count"),
            "fetched_at": time.time(), "reels": reels[:want]}
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    (RAW_DIR / f"{username}.json").write_text(json.dumps(data, ensure_ascii=False, indent=1))
    return data


APIFY_ACTOR = "https://api.apify.com/v2/acts/apify~instagram-reel-scraper/run-sync-get-dataset-items"


def _epoch(ts):
    if isinstance(ts, (int, float)):
        return ts
    try:
        return datetime.fromisoformat(str(ts).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return 0


def fetch_account_apify(username, want):
    """One Apify run per account (the official Instagram Reel Scraper)."""
    # The token is either an env var, or added by a Claude Code network secret
    # (Authorization: Bearer on api.apify.com) — then it's blank here.
    token = env("APIFY_TOKEN", required=False)
    resp = requests.post(APIFY_ACTOR, json={"username": [username], "resultsLimit": want},
                         headers={"Authorization": f"Bearer {token}"} if token else {}, timeout=600)
    if resp.status_code in (401, 403):
        raise SystemExit("Apify rejected the token (401/403). Check the Apify secret: header "
                         "Authorization, prefix Bearer, value = your Apify API token.")
    if resp.status_code == 402:
        raise SystemExit("Apify account is out of credit. Top up at console.apify.com/billing.")
    resp.raise_for_status()
    reels = []
    for item in resp.json():
        if item.get("error"):
            continue
        code = item.get("shortCode") or item.get("code")
        if not code:
            continue
        reels.append({
            "code": code,
            "url": item.get("url") or f"https://www.instagram.com/reel/{code}/",
            "views": item.get("videoPlayCount") or item.get("videoViewCount") or 0,
            "likes": item.get("likesCount") or 0,
            "comments": item.get("commentsCount") or 0,
            "taken_at": _epoch(item.get("timestamp")),
            "post_caption": (item.get("caption") or "")[:300],
            "video": item.get("videoUrl"),
            "thumbnail": item.get("displayUrl"),
        })
    if not reels:
        print(f"  ! @{username}: no reels returned (private, renamed, or no reels)")
        return None
    reels.sort(key=lambda r: r["taken_at"], reverse=True)
    data = {"username": username, "followers": None, "fetched_at": time.time(), "reels": reels[:want]}
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    (RAW_DIR / f"{username}.json").write_text(json.dumps(data, ensure_ascii=False, indent=1))
    return data


def find_outliers(accounts, radar):
    """Reels that beat their creator's MEDIAN views (median, so one freak hit doesn't hide the rest)."""
    now = time.time()
    min_age = radar["min_age_hours"] * 3600
    max_age = radar["max_age_days"] * 86400
    outliers = []
    for acc in accounts:
        window = [r for r in acc["reels"] if min_age <= now - r["taken_at"] <= max_age]
        if len(window) < 5:
            continue  # not enough reels to trust a baseline
        median = statistics.median(r["views"] for r in window) or 1
        for r in window:
            ratio = r["views"] / median
            beats_bar = (ratio >= radar["min_ratio"]
                         or (ratio >= radar["hybrid_ratio"] and r["views"] >= radar["hybrid_min_views"]))
            if beats_bar and r["views"] >= radar["abs_floor_views"]:
                outliers.append({**r, "account": acc["username"], "ratio": round(ratio, 1),
                                 "median": int(median)})
    return sorted(outliers, key=lambda r: r["ratio"], reverse=True)


def run(competitors, radar, use_cache=False):
    accounts = []
    for c in competitors:
        name = c["username"] if isinstance(c, dict) else c
        cached = RAW_DIR / f"{name}.json"
        if use_cache and cached.exists():
            accounts.append(json.loads(cached.read_text()))
            continue
        fetch = fetch_account if radar.get("source") == "hiker" else fetch_account_apify
        acc = fetch(name, radar["reels_per_account"])
        if acc:
            print(f"  ✓ @{name}: {len(acc['reels'])} reels, {acc.get('followers') or '?'} followers")
            accounts.append(acc)

    _print_distribution(accounts)
    outliers = find_outliers(accounts, radar)
    print(f"\n  {len(outliers)} outlier reels found. Reading their on-screen text…")
    texts = vision.read_reels([{"key": f"comp:{o['code']}", "video": o["video"],
                                "thumbnail": o["thumbnail"]} for o in outliers])
    for o in outliers:
        seen = texts.get(f"comp:{o['code']}", {})
        o["on_screen_text"] = seen.get("on_screen_text")
        o["visual"] = seen.get("visual")
        o.pop("video", None)  # signed URLs expire; don't keep them
        o.pop("thumbnail", None)
    DATA.mkdir(exist_ok=True)
    OUTLIERS.write_text(json.dumps(outliers, ensure_ascii=False, indent=1))
    return outliers


def _print_distribution(accounts):
    """Helps you tune the view floors in config.yaml to your niche."""
    print("\n  Typical views per account (median of last reels):")
    for acc in accounts:
        views = [r["views"] for r in acc["reels"]]
        if views:
            print(f"    @{acc['username']:<24} median {int(statistics.median(views)):>9,}   best {max(views):>11,}")


def load():
    return json.loads(OUTLIERS.read_text()) if OUTLIERS.exists() else []
