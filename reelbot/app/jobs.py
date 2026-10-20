"""ReelBot's engine: analyse clips, research, make reels, post on time and track results.

Heavy work (video, AI) goes through one background worker so nothing runs twice at once.
A scheduler thread handles the clock: posting, 24/48/72h results, daily autopilot, weekly research.
"""

import copy
import json
import math
import os
import queue
import re
import statistics
import threading
import tempfile
import time
import traceback
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

from .. import competitors, editor, vision
from ..settings import DATA, claude_key, env, load_config
from . import brain, db

# --------------------------------------------------------------------------- settings

EDITABLE = {  # setting key -> (path in config.yaml, label)
    "mode": ("mode", "Mode"),
    "niche": ("niche", "About my account"),
    "posts_per_day": ("autopilot.posts_per_day", "Reels per day"),
    "mix_instagram": ("research_mix.instagram", "Research mix: Instagram (%)"),
    "mix_tiktok": ("research_mix.tiktok", "Research mix: TikTok (%)"),
    "mix_trends": ("research_mix.trends", "Research mix: news & Google trends, riskier (%)"),
    "mix_original": ("research_mix.original", "Research mix: original, trend-setting (%)"),
    "mix_auto": ("research_mix.auto_balance", "Rebalance the mix from results"),
    "times_mode": ("autopilot.times_mode", "Posting times"),
    "post_times": ("autopilot.post_times", "Manual posting times"),
    "reels_per_clip": ("clips.variants_per_clip", "Reels per clip"),
    "research_refresh_days": ("research_refresh_days", "Reuse research for (days)"),
    "research_budget": ("research_budget_usd", "Paid research budget ($ a month)"),
    "radar_source": ("radar.source", "Competitor checks"),
    "apify_mode": ("research_apify", "Apify (paid research)"),
    "reel_seconds": ("clips.reel_seconds", "Reel length (s)"),
    "text_style": ("look.text_style", "Text style"),
    "grade": ("look.grade", "Colour look"),
    "broll_silent": ("clips.broll_silent", "B-roll silent"),
    "hashtags": ("posting.hashtags", "Hashtags on every post"),
    "competitors": ("competitors", "Competitors"),
}


def _get(d, path):
    for part in path.split("."):
        d = d.get(part, {}) if isinstance(d, dict) else {}
    return d if d != {} else None


def _set(d, path, value):
    parts = path.split(".")
    for part in parts[:-1]:
        d = d.setdefault(part, {})
    d[parts[-1]] = value


def cfg():
    """config.yaml with anything changed in the app's Settings page on top."""
    c = copy.deepcopy(load_config())
    for key, (path, _) in EDITABLE.items():
        value = db.get_setting(key)
        if value is not None:
            _set(c, path, value)
    c.setdefault("autopilot", {}).setdefault("times_mode", "best")
    c.setdefault("research_mix", {"instagram": 40, "tiktok": 25, "trends": 15, "original": 20, "auto_balance": True})
    c.setdefault("clips", {}).setdefault("broll_silent", True)
    c["audio"]["folder"] = str(db.AUDIO_DIR)
    return c


def setting(key):
    return _get(cfg(), EDITABLE[key][0])


def tz():
    return ZoneInfo(cfg()["posting"].get("timezone", "Europe/London"))


def local_now():
    return datetime.now(tz()).replace(tzinfo=None, second=0, microsecond=0)


# --------------------------------------------------------------------------- worker

_tasks = queue.Queue()


def submit(name, fn, *args):
    _tasks.put((name, fn, args))


def _worker():
    while True:
        name, fn, args = _tasks.get()
        try:
            fn(*args)
        except Exception as e:  # keep the worker alive; show the problem in the app
            db.log(f"✗ {name} failed: {e}")
            traceback.print_exc()


def busy():
    return _tasks.qsize()


# --------------------------------------------------------------------------- clips

def _frames(path, n=3, start=0.0, length=None):
    duration, _ = editor.probe(path)
    length = length or duration
    out = []
    for i in range(n):
        f = vision._frame_from_video(path, start + length * (i + 0.5) / n)
        if f:
            out.append(f)
    return out


def add_clip(path, filename, kind=None, description="", keep_look=False, batch=None):
    clip_id = db.new_id()
    duration, _ = editor.probe(path)
    db.insert("clips", {"id": clip_id, "filename": filename, "path": str(path), "duration": duration,
                        "description": description.strip() or None, "keep_look": 1 if keep_look else 0,
                        "batch": batch, "combine": 1 if batch and (db.get_setting(f"batch:{batch}") or {}).get("combine") else 0,
                        "kind": kind or "main", "notes": "kind set by you" if kind else "",
                        "broll_silent": 1 if setting("broll_silent") else 0})
    submit(f"analyse {filename}", analyse_clip, clip_id, kind is None)
    return clip_id


def ensure_working_copy(clip):
    """Swap a 4K original for a 1080p working copy (and delete the original to save space)."""
    path = Path(clip["path"])
    if not path.exists():
        return clip
    small = editor.working_copy(path)
    if small != path:
        path.unlink(missing_ok=True)
        db.update("clips", clip["id"], path=str(small))
        clip = {**clip, "path": str(small)}
    return clip


def analyse_clip(clip_id, decide_kind=True, make_after=True):
    clip = db.one("SELECT * FROM clips WHERE id = ?", clip_id)
    db.update("clips", clip_id, status="analysing")
    clip = ensure_working_copy(clip)
    duration, has_audio = editor.probe(clip["path"])
    loud = editor.loudest_start(clip["path"], duration, min(8, duration)) + 1.0 if has_audio else 0.0
    try:
        info = brain.analyse_clip(_frames(clip["path"], 4), duration, has_audio, loud, cfg()["niche"], clip["description"] or "")
    except Exception as e:  # don't leave it "analysing" forever
        db.update("clips", clip_id, status="failed", notes=f"Analysis failed: {str(e)[:300]}")
        raise
    fields = {"subject": info["subject"], "hashtags": json.dumps(info["hashtags"]), "status": "analysed",
              "search_terms": json.dumps(info.get("search_terms", [])),
              "notes": f"{info['mood']} · {info['highlight']}"}
    if decide_kind:
        fields["kind"] = info["kind"]
        fields["notes"] += f" · {info['kind']}: {info['kind_reason']}"
    db.update("clips", clip_id, **fields)
    db.log(f"Analysed {clip['filename']}: {info['subject']} ({fields.get('kind', clip['kind'])})")
    if clip["batch"]:
        batch_ready(clip["batch"])
    elif make_after and fields.get("kind", clip["kind"]) == "main" and setting("mode") == "review":
        submit(f"make reels for {clip['filename']}", make_reels, clip_id)


# --------------------------------------------------------------------------- research

APIFY_HASHTAG = "https://api.apify.com/v2/acts/apify~instagram-hashtag-scraper/run-sync-get-dataset-items"


def _apify_headers():
    token = env("APIFY_TOKEN", required=False)
    return {"Authorization": f"Bearer {token}"} if token else {}


def _apify_run(url, payload, expected=0, per_result=0.003):
    """Run an Apify actor and return its items, if this month's budget allows it.
    expected = roughly how many results it returns (for the budget check). Says what went wrong, e.g. "limit exceeded"."""
    spend_check(expected * per_result)
    resp = requests.post(url, json=payload, headers=_apify_headers(), timeout=900)
    _count("apify_runs")
    if not resp.ok:
        try:
            message = resp.json()["error"]["message"]
        except Exception:
            message = resp.reason
        raise RuntimeError(f"Apify {resp.status_code}: {message}")
    items = resp.json()
    spent(len(items) * per_result)
    return items


# --------------------------------------------------------------------------- research budget
# Apify searches cost money. Before each one ReelBot checks this month's real Apify spend and stops at your budget
# (Settings → Paid research budget), then falls back to research it has already saved.

APIFY_LIMITS = "https://api.apify.com/v2/users/me/limits"
PRICE = {"instagram": 0.003, "tiktok": 0.005}  # rough $ per result, only used until Apify reports the real spend


class OverBudget(RuntimeError):
    pass


def apify_spend(fresh=False):
    """This month's Apify spend: Apify's own figure when it answers, otherwise ReelBot's running estimate."""
    cached = db.get_setting("apify_spend")
    if cached and not fresh and time.time() - cached["at"] < 600:
        return cached
    est = round(float(db.get_setting(f"apify_est:{local_now():%Y-%m}", 0)), 2)
    out = {"usd": est, "from": "estimate", "resets": None, "at": time.time()}
    if env("APIFY_TOKEN", required=False):
        try:
            r = requests.get(APIFY_LIMITS, headers=_apify_headers(), timeout=20)
            if r.ok:
                d = r.json()["data"]
                out = {"usd": round(float(d["current"]["monthlyUsageUsd"]), 2), "from": "apify", "at": time.time(),
                       "resets": (d.get("monthlyUsageCycle") or {}).get("endAt"),
                       "apify_cap": (d.get("limits") or {}).get("maxMonthlyUsageUsd")}
        except Exception:
            pass
    db.set_setting("apify_spend", out)
    return out


def spend_check(cost):
    budget = float(setting("research_budget") or 0)
    now = apify_spend()
    if now["usd"] + cost > budget:
        raise OverBudget(f"monthly research budget reached (${now['usd']:.2f} of ${budget:.2f} spent), "
                         "so Creatr used research it had already saved")


def spent(cost):
    key = f"apify_est:{local_now():%Y-%m}"
    db.set_setting(key, round(float(db.get_setting(key, 0)) + cost, 4))
    now = apify_spend()  # Apify's own figure can lag a few minutes: add this run to it until it catches up
    db.set_setting("apify_spend", now | {"usd": round(now["usd"] + cost, 2)})


def _count(name):
    """Monthly counters, e.g. how many paid scrapes ran vs how often the library was reused."""
    key = f"{name}:{local_now():%Y-%m}"
    db.set_setting(key, int(db.get_setting(key, 0)) + 1)


# --------------------------------------------------------------------------- research library
# Every reel ReelBot researches (and every link you save) is kept here, so research is paid for once
# and reused by every clip on the same topic. Later this is what makes ReelBot cheaper per customer.

def _tags(hashtags):
    return sorted({h.lstrip("#").lower() for h in hashtags if h})


def library_add(reels, platform, source, tags=(), note=None):
    for r in reels:
        rid = f"{platform}:{r['code']}"
        old = db.one("SELECT * FROM library WHERE id = ?", rid)
        merged = sorted(set(json.loads(old["tags"] or "[]") if old else []) | set(tags))
        row = {"id": rid, "platform": platform, "url": r.get("url"), "creator": r.get("account"),
               "views": r.get("views"), "likes": r.get("likes"), "shares": r.get("shares"), "music": r.get("music"),
               "on_screen_text": r.get("on_screen_text") or (old or {}).get("on_screen_text"),
               "post_caption": (r.get("post_caption") or "")[:300], "tags": json.dumps(merged),
               "source": "saved" if (old and old["source"] == "saved") or source == "saved" else source,
               "note": note if note is not None else (old or {}).get("note"), "status": "ok",
               "posted_at": datetime.fromtimestamp(r["taken_at"]).isoformat(timespec="minutes") if r.get("taken_at") else None,
               "first_seen": (old or {}).get("first_seen") or db.now(), "last_seen": db.now()}
        db.insert("library", row)


def _reuse(prefix, tags, days):
    """A recent research run whose hashtags overlap these enough to reuse (saves a paid scrape)."""
    since = (datetime.now(ZoneInfo("UTC")) - timedelta(days=days)).isoformat(timespec="seconds")
    need = 1 if tags else 99
    for row in db.q("SELECT data FROM research WHERE account = ? AND kind LIKE ? AND created_at >= ? ORDER BY created_at DESC",
                    db.ACCOUNT, prefix + ":%", since):
        data = json.loads(row["data"])
        if len(set(data.get("hashtags", [])) & set(tags)) >= need:
            _count("library_reuse")
            return data
    return None


def saved_topic(tags, subject, platform="instagram", days=90):
    """Research already in the library for these hashtags (free): stands in when a paid search can't run."""
    since = (datetime.now(ZoneInfo("UTC")) - timedelta(days=days)).isoformat(timespec="seconds")
    rows = [r for r in db.q("SELECT * FROM library WHERE account = ? AND platform = ? AND last_seen >= ? AND views > 0",
                            db.ACCOUNT, platform, since)
            if set(json.loads(r["tags"] or "[]")) & set(tags) or r["source"] == "saved"]
    rows.sort(key=lambda r: (r["source"] != "saved", -(r["views"] or 0)))
    if not rows:
        return None
    winners = [{"code": r["id"].split(":", 1)[1], "url": r["url"], "account": r["creator"], "views": r["views"] or 0,
                "likes": r["likes"] or 0, "shares": r["shares"] or 0, "music": r["music"], "post_caption": r["post_caption"] or "",
                "on_screen_text": r["on_screen_text"] or ""} for r in rows[:12]]
    sounds = Counter(r["music"] for r in rows if r["music"] and r["music"] not in ("original audio", "?"))
    original = sum(1 for r in rows if r["music"] == "original audio")
    return {"checked_at": local_now().isoformat(), "hashtags": tags, "subject": subject, "found": len(rows),
            "winners": winners, "trending_sounds": sounds.most_common(10), "sounds": sounds.most_common(8), "sounds_7d": [],
            "recent_7d": 0, "original_audio_share": round(original / max(len(rows), 1), 2), "from_library": True}


def save_links(text, note=""):
    """Reels you liked: store the links now, then fetch their stats and on-screen text in the background."""
    urls = [u.strip() for u in text.replace(",", " ").split() if u.strip().startswith("http")]
    ids = []
    for url in urls:
        platform = "tiktok" if "tiktok.com" in url else "instagram"
        code = url.rstrip("/").split("/")[-1].split("?")[0]
        ids.append(f"{platform}:{code}")
        old = db.one("SELECT id FROM library WHERE id = ?", ids[-1])
        if old:
            db.update("library", ids[-1], source="saved", note=note or None)
        else:
            db.insert("library", {"id": ids[-1], "platform": platform, "url": url, "source": "saved", "note": note or None,
                                  "status": "fetching", "tags": "[]", "first_seen": db.now(), "last_seen": db.now()})
    if ids:
        submit("fetch saved reels", fetch_saved, ids)
        db.log(f"Saved {len(ids)} reel link(s) to the research library")
    return len(ids)


def fetch_saved(ids):
    rows = [db.one("SELECT * FROM library WHERE id = ?", i) for i in ids]
    ig = [r for r in rows if r and r["platform"] == "instagram"]
    tt = [r for r in rows if r and r["platform"] == "tiktok"]
    found = []
    try:
        if ig:
            items = _apify_run(APIFY_POSTS, {"directUrls": [r["url"] for r in ig], "resultsType": "posts", "resultsLimit": len(ig)},
                               len(ig), PRICE["instagram"])
            found += [("instagram", x) for x in (competitors.apify_reel(i) for i in items) if x]
        if tt:
            items = _apify_run(APIFY_TIKTOK, {"postURLs": [r["url"] for r in tt], "shouldDownloadVideos": False,
                                              "shouldDownloadCovers": False}, len(tt), PRICE["tiktok"])
            found += [("tiktok", x) for x in (_tiktok_video(i) for i in items) if x]
    except Exception as e:
        db.log(f"Couldn't fetch saved reels' stats (kept the links): {e}")
    for _, r in found:
        r["frame_bytes"] = vision.gather_frames(r.get("video"), r.get("thumbnail"))[:2]
    reads = _read([r for _, r in found if r["frame_bytes"]], "reels the creator saved as inspiration")
    for platform, r in found:
        r["on_screen_text"] = reads.get(r["code"], {}).get("on_screen_text", "")
        library_add([r], platform, "saved")
    fetched = {f"{p}:{r['code']}" for p, r in found}
    for r in rows:
        if r and r["id"] not in fetched and r["status"] == "fetching":
            db.update("library", r["id"], status="link only")


def _read(reels, subject):
    """Claude reads the reels' on-screen text. If that fails, keep the (paid) research without the text."""
    if not reels:
        return {}
    try:
        return {x["code"]: x for x in brain.read_reels(reels, subject)}
    except Exception as e:
        db.log(f"Reading research reels skipped: {e}")
        return {}


# Research order, cheapest first: Instagram's own hashtag search (free) → reels found on the web via Claude's web
# search (pennies) → Apify (paid, last resort: only when the free sources found too little, and inside the budget).

def ig_hashtag_top(tags, want=25):
    """Instagram's own hashtag search (free, official): top reels for each hashtag. Likes, not views.
    Instagram allows 30 different hashtags a week per account, so hashtag ids are remembered."""
    graph = f"https://graph.facebook.com/{cfg()['posting']['graph_api_version']}"
    uid, ids, reels = env("IG_USER_ID", required=False), db.get_setting("ig_hashtag_ids") or {}, []
    if not uid:
        raise RuntimeError("Instagram isn't connected (IG_USER_ID)")
    for tag in tags:
        if tag not in ids:
            r = requests.get(f"{graph}/ig_hashtag_search", params={"user_id": uid, "q": tag, **_ig_auth()}, timeout=30)
            if not r.ok or not r.json().get("data"):
                raise RuntimeError(f"Instagram hashtag search: {(r.json().get('error') or {}).get('message', r.reason) if r.content else r.reason}")
            ids[tag] = r.json()["data"][0]["id"]
            db.set_setting("ig_hashtag_ids", ids)
        r = requests.get(f"{graph}/{ids[tag]}/top_media", params={
            "user_id": uid, "limit": 50, **_ig_auth(),
            "fields": "id,media_type,like_count,comments_count,caption,permalink,timestamp,media_url"}, timeout=30)
        if not r.ok:
            raise RuntimeError(f"Instagram top reels for #{tag}: {(r.json().get('error') or {}).get('message', r.reason) if r.content else r.reason}")
        for m in r.json().get("data", []):
            if m.get("media_type") != "VIDEO" or not m.get("permalink"):
                continue
            reels.append({"code": m["permalink"].rstrip("/").split("/")[-1], "url": m["permalink"], "account": None,
                          "views": int(m.get("like_count") or 0), "likes": int(m.get("like_count") or 0), "metric": "likes",
                          "comments": int(m.get("comments_count") or 0), "taken_at": competitors._epoch(m.get("timestamp")),
                          "post_caption": (m.get("caption") or "")[:300], "music": None, "video": m.get("media_url")})
    seen = set()
    return [r for r in sorted(reels, key=lambda r: -r["views"]) if not (r["code"] in seen or seen.add(r["code"]))][:want]


def web_found(subject, terms, platform):
    """Reels or TikToks found on the web for a topic (Claude's web search), as research items without numbers."""
    sites = ("instagram.com",) if platform == "instagram" else ("tiktok.com",)
    _count("web_searches")
    out, seen = [], set()
    for r in brain.web_reels(subject, terms, sites):
        url = r["url"].split("?")[0]
        m = re.search(r"instagram\.com/(?:[\w.]+/)?(?:reel|reels|p)/([\w-]+)", url) or re.search(r"tiktok\.com/@([\w.]+)/video/(\d+)", url)
        if not m or url in seen:
            continue
        seen.add(url)
        title = r["title"]
        if platform == "tiktok":
            account, code = m.group(1), m.group(2)
        else:
            code = m.group(1)
            who = re.search(r"\(@([\w.]+)\)", title) or re.match(r"([\w.]+) on Instagram", title)
            account = who.group(1) if who else None
        caption = title.split(":", 1)[1].strip(' "“”') if ":" in title else title
        out.append({"code": code, "url": url, "account": account, "views": 0, "likes": 0, "shares": 0, "metric": "found on the web",
                    "music": None, "post_caption": caption[:300], "on_screen_text": "", "taken_at": None, "via": "web"})
    out = out[:10]
    if platform == "tiktok":  # TikTok's free embed info gives the cover image, so the on-screen text can still be read
        for v in out:
            try:
                info = requests.get("https://www.tiktok.com/oembed", params={"url": v["url"]}, timeout=15).json()
                v["thumbnail"] = info.get("thumbnail_url")
                v["post_caption"] = (info.get("title") or v["post_caption"])[:300]
            except Exception:
                pass
    return out


def apify_allowed():
    return bool(env("APIFY_TOKEN", required=False)) and (setting("apify_mode") or "last_resort") != "off"


def research_topic(hashtags, subject, per_tag=20, terms=()):
    """Top recent reels for this clip's topic, with their on-screen text. Free sources first; Apify only as a last
    resort. Reuses a recent run on overlapping hashtags (see research_refresh_days)."""
    tags = _tags(hashtags)[:2]
    cached = _reuse("topic", tags, int(setting("research_refresh_days") or 7))
    if cached:
        return cached
    reels, web, via, problems = [], [], [], []
    try:
        reels = ig_hashtag_top(tags)
        via.append("Instagram hashtag search (free)")
    except Exception as e:
        problems.append(str(e)[:160])
    try:
        web = web_found(subject, list(terms) or tags, "instagram")
        via.append("web search")
    except Exception as e:
        problems.append(f"web search: {str(e)[:120]}")
    if len(reels) + len(web) < 5 and apify_allowed():  # the free sources came up short: pay, if the budget allows
        try:
            items = _apify_run(APIFY_HASHTAG, {"hashtags": tags, "resultsType": "reels", "resultsLimit": per_tag},
                               len(tags) * per_tag, PRICE["instagram"])
            reels = [r for r in (competitors.apify_reel(i) for i in items) if r]
            via.append("Apify (paid, last resort)")
        except RuntimeError as e:
            problems.append(str(e)[:160])
    if not reels and not web:
        saved = saved_topic(tags, subject)
        if saved:
            db.log(f"Instagram research: nothing new ({'; '.join(problems)}), using {len(saved['winners'])} saved reels")
            return saved
        raise RuntimeError("; ".join(problems) or "nothing found")
    cutoff = time.time() - 60 * 86400
    reels = [r for r in reels if r["taken_at"] >= cutoff]
    reels.sort(key=lambda r: r["views"], reverse=True)
    top = reels[:12]
    for r in top:
        r["frame_bytes"] = vision.gather_frames(r.get("video"), r.get("thumbnail"))[:2]
    reads = _read(top, subject)
    winners = []
    for r in top:
        read = reads.get(r["code"], {})
        if read.get("relevant", True):
            winners.append({k: r.get(k) for k in ("code", "url", "account", "views", "likes", "music", "post_caption")}
                           | {"on_screen_text": read.get("on_screen_text", ""), "metric": r.get("metric", "views")})
    winners += web[: max(0, 14 - len(winners))]
    library_add([w | {"taken_at": next((r["taken_at"] for r in top if r["code"] == w["code"]), None)} for w in winners],
                "instagram", "research", tags)
    sounds = Counter(r["music"] for r in reels[:30] if r.get("music") and r["music"] != "original audio")
    week = time.time() - 7 * 86400
    sounds_7d = Counter(r["music"] for r in reels if r["taken_at"] >= week and r.get("music") and r["music"] != "original audio")
    with_music = [r for r in reels[:30] if r.get("music")]
    original = sum(1 for r in with_music if r["music"] == "original audio")
    result = {"checked_at": local_now().isoformat(), "hashtags": tags, "subject": subject, "via": via, "problems": problems,
              "found": len(reels) + len(web), "winners": winners, "trending_sounds": sounds.most_common(10),
              "sounds_7d": sounds_7d.most_common(10), "recent_7d": sum(1 for r in reels if r["taken_at"] >= week),
              "original_audio_share": round(original / len(with_music), 2) if with_music else None}
    db.save_research("topic:" + ",".join(tags), result)
    db.save_research("topic", result)
    db.log(f"Researched #{' #'.join(tags)} via {', '.join(via)}: {len(winners)} relevant winners")
    return result


APIFY_POSTS = "https://api.apify.com/v2/acts/apify~instagram-scraper/run-sync-get-dataset-items"
APIFY_TIKTOK = "https://api.apify.com/v2/acts/clockworks~tiktok-scraper/run-sync-get-dataset-items"


def _tiktok_video(item):
    if not item.get("id") or not item.get("playCount"):
        return None
    music = item.get("musicMeta") or {}
    return {"code": str(item["id"]), "url": item.get("webVideoUrl"), "account": (item.get("authorMeta") or {}).get("name", ""),
            "views": int(item.get("playCount") or 0), "likes": int(item.get("diggCount") or 0),
            "shares": int(item.get("shareCount") or 0), "taken_at": int(item.get("createTime") or 0),
            "post_caption": item.get("text") or "", "thumbnail": (item.get("videoMeta") or {}).get("coverUrl"),
            "music": "original audio" if music.get("musicOriginal") else
                     " — ".join(x for x in (music.get("musicName"), music.get("musicAuthor")) if x) or "?"}


def research_tiktok(hashtags, subject, per_tag=15, terms=()):
    """Top TikToks for this topic: found on the web first (pennies); Apify (paid, has views and rising sounds) only
    when that finds too little. At most once a week a topic."""
    tags = _tags(hashtags)[:2]
    if not tags:
        return None
    key = "tiktok:" + ",".join(tags)
    cached = _reuse("tiktok", tags, max(7, int(setting("research_refresh_days") or 7)))
    if cached:
        return cached
    web, problems = [], []
    try:
        web = web_found(subject, list(terms) or tags, "tiktok")
    except Exception as e:
        problems.append(f"web search: {str(e)[:120]}")
    items = None
    if len(web) < 4 and apify_allowed():
        try:
            items = _apify_run(APIFY_TIKTOK, {
                "hashtags": tags, "resultsPerPage": per_tag, "shouldDownloadVideos": False, "shouldDownloadCovers": False,
                "shouldDownloadSubtitles": False, "shouldDownloadSlideshowImages": False}, len(tags) * per_tag, PRICE["tiktok"])
        except RuntimeError as e:
            problems.append(str(e)[:160])
    if items is None:
        if not web:
            saved = saved_topic(tags, subject, "tiktok")
            if saved:
                return saved
            raise RuntimeError("; ".join(problems) or "nothing found")
        for v in web:
            v["frame_bytes"] = vision.gather_frames(None, v.get("thumbnail"))[:1]
        reads = _read([v for v in web if v["frame_bytes"]], subject)
        web = [{k: v[k] for k in v if k not in ("frame_bytes", "thumbnail")} | {"on_screen_text": reads.get(v["code"], {}).get("on_screen_text", "")}
               for v in web if reads.get(v["code"], {}).get("relevant", True)]
        result = {"checked_at": local_now().isoformat(), "hashtags": tags, "subject": subject, "found": len(web),
                  "winners": web, "sounds": [], "sounds_7d": [], "original_audio_share": None, "via": ["web search"]}
        library_add(web, "tiktok", "research", tags)
        db.save_research(key, result)
        db.save_research("tiktok", result)
        db.log(f"TikTok research #{' #'.join(tags)}: {len(web)} found on the web")
        return result
    cutoff, week = time.time() - 30 * 86400, time.time() - 7 * 86400
    seen, videos = set(), []
    for v in (_tiktok_video(i) for i in items):
        if v and v["taken_at"] >= cutoff and v["code"] not in seen:
            seen.add(v["code"])
            videos.append(v)
    videos.sort(key=lambda v: v["views"], reverse=True)
    top = videos[:12]
    for v in top:
        v["frame_bytes"] = vision.gather_frames(None, v.get("thumbnail"))[:1]
    reads = _read([v for v in top if v["frame_bytes"]], subject)
    winners = [{k: v.get(k) for k in ("code", "url", "account", "views", "likes", "shares", "music", "post_caption")}
               | {"on_screen_text": reads.get(v["code"], {}).get("on_screen_text", "")}
               for v in top if reads.get(v["code"], {}).get("relevant", True)]
    winners += web[: max(0, 12 - len(winners))]  # keep what the web search found too
    sounds = lambda vs: Counter(v["music"] for v in vs if v["music"] not in ("original audio", "?")).most_common(8)
    result = {"checked_at": local_now().isoformat(), "hashtags": tags, "subject": subject, "found": len(videos),
              "winners": winners, "sounds": sounds(videos), "sounds_7d": sounds([v for v in videos if v["taken_at"] >= week]),
              "original_audio_share": round(sum(v["music"] == "original audio" for v in videos[:30]) / max(len(videos[:30]), 1), 2)}
    result["via"] = (["web search"] if web else []) + ["Apify (paid, last resort)"]
    library_add([w | {"taken_at": None} for w in winners], "tiktok", "research", tags)
    db.save_research(key, result)
    db.save_research("tiktok", result)
    db.log(f"TikTok research #{' #'.join(tags)}: {len(winners)} winners, {len(result['sounds_7d'])} rising sounds")
    return result


TRENDS_RSS = "https://trends.google.com/trending/rss?geo={geo}"
HT = "{https://trends.google.com/trending/rss}"


def google_trends(max_age_hours=6):
    """What people are searching on Google right now (UK + US), with the headline behind each. Free RSS feed."""
    cached = db.latest_research("trends")
    if cached and datetime.fromisoformat(cached["checked_at"]) > local_now() - timedelta(hours=max_age_hours):
        return cached
    items = []
    for geo in ("GB", "US"):
        try:
            root = ET.fromstring(requests.get(TRENDS_RSS.format(geo=geo), timeout=30).content)
        except Exception as e:
            db.log(f"Google trends ({geo}) skipped: {e}")
            continue
        for it in root.iter("item"):
            news = it.find(f"{HT}news_item")
            items.append({"geo": geo, "term": it.findtext("title", ""),
                          "searches": it.findtext(f"{HT}approx_traffic", ""),
                          "headline": news.findtext(f"{HT}news_item_title", "") if news is not None else "",
                          "url": news.findtext(f"{HT}news_item_url", "") if news is not None else ""})
    if not items:
        return cached
    result = {"checked_at": local_now().isoformat(), "items": items}
    db.save_research("trends", result)
    db.log(f"Google trends: {len(items)} trending searches")
    return result


def trend_news(max_age_hours=6):
    """What the UK is talking about this week, from Claude's web search (news, films, games, launches, memes)."""
    cached = db.latest_research("news")
    if cached and datetime.fromisoformat(cached["checked_at"]) > local_now() - timedelta(hours=max_age_hours):
        return cached
    _count("web_searches")
    seen, items = set(), []
    for r in brain.web_news():
        title = (r["title"] or "").split(" | ")[0].split(" - ")[0].strip()
        if title and title.lower() not in seen:
            seen.add(title.lower())
            items.append({"title": title[:140], "url": r["url"]})
    result = {"checked_at": local_now().isoformat(), "items": items[:25]}
    db.save_research("news", result)
    db.log(f"Trend news: {len(result['items'])} stories people are talking about")
    return result


TREND_LEVELS = [(50, "deepest"), (25, "deeper"), (1, "light")]  # Trends share of the mix → how hard to hunt


def trend_hunt(clip, share):
    """Trend-jacking, scaled by the Trends slider: light = Google's trending searches only; deeper = Claude also links
    them to this clip as ready-made hooks; deepest = adds this week's news and pop culture from the web, more ideas."""
    level = next((name for floor, name in TREND_LEVELS if share >= floor), None)
    if level in (None, "light"):
        return {"level": level, "share": share, "ideas": [], "news": []}
    trends = (db.latest_research("trends") or {}).get("items", [])[:30]
    news = []
    if level == "deepest":
        try:
            news = trend_news()["items"]
        except Exception as e:
            db.log(f"Trend news skipped: {e}")
    lines = [f'[G{i}] {t["term"]} · {t["searches"]} searches ({t["geo"]}) · {t["headline"][:100]}' for i, t in enumerate(trends, 1)]
    lines += [f'[N{i}] {n["title"]}' for i, n in enumerate(news, 1)]
    if not lines:
        return {"level": level, "share": share, "ideas": [], "news": news}
    ideas = brain.trend_ideas(_frames(clip["path"], 2), clip["subject"], cfg()["niche"], "\n".join(lines),
                              8 if level == "deepest" else 5)
    for idea in ideas:  # attach the real trend behind each idea (and drop made-up ids)
        ref = (idea["ref"] or "").strip("[] ").upper()
        idx = int(ref[1:]) - 1 if ref[1:].isdigit() else -1
        src = (trends if ref.startswith("G") else news if ref.startswith("N") else [])
        idea["source"] = src[idx] if 0 <= idx < len(src) else None
    ideas = [i for i in ideas if i["source"] and i["fit"] >= 5]
    ideas.sort(key=lambda i: -i["fit"])
    return {"level": level, "share": share, "ideas": ideas, "news": news}


SUGGEST = "https://suggestqueries.google.com/complete/search"


def _suggest(query, youtube=False):
    params = {"client": "firefox", "hl": "en-GB", "gl": "gb", "q": query} | ({"ds": "yt"} if youtube else {})
    resp = requests.get(SUGGEST, params=params, timeout=15)
    resp.raise_for_status()
    return [x for x in resp.json()[1] if x.lower() != query.lower()]


def google_keywords(terms, days=7):
    """What people actually type into Google and YouTube about this clip's topic (free autocomplete, UK).
    Each phrase is checked as typed, plus as a question, and kept for a week."""
    since = (datetime.now(ZoneInfo("UTC")) - timedelta(days=days)).isoformat(timespec="seconds")
    items, errors = [], []
    for term in [t.strip().lower() for t in terms if t and t.strip()][:3]:
        row = db.one("SELECT data FROM research WHERE account = ? AND kind = ? AND created_at >= ? ORDER BY created_at DESC",
                     db.ACCOUNT, "keywords:" + term, since)
        if row:
            items += json.loads(row["data"])["items"]
            continue
        found = []
        try:
            for q, where in ((term, "google"), (term, "youtube"), ("why " + term, "google"), (term + " vs", "google")):
                found += [{"term": term, "search": x, "where": where} for x in _suggest(q, where == "youtube")[:6]]
        except Exception as e:
            errors.append(f"{term}: {e}")
        if found:
            db.save_research("keywords:" + term, {"checked_at": local_now().isoformat(), "items": found})
        items += found
    seen, out = set(), []
    for it in items:
        if it["search"].lower() not in seen:
            seen.add(it["search"].lower())
            out.append(it)
    if errors and not out:
        raise RuntimeError("; ".join(errors)[:200])
    return {"terms": terms[:3], "items": out[:30]}


def run_radar():
    """Weekly: competitor reels that beat their own normal views, with their on-screen text."""
    c = cfg()
    radar = c["radar"] | {"api_version": c["posting"]["graph_api_version"]}
    if radar.get("source") == "apify":  # paid: smaller pulls, inside the monthly budget
        radar["reels_per_account"] = min(radar["reels_per_account"], 20)
    outliers = competitors.run(c["competitors"], radar, before_paid=lambda n: spend_check(n * PRICE["instagram"]),
                               after_paid=lambda n: spent(n * PRICE["instagram"]))
    library_add([o | {"code": o.get("code") or o.get("url", "").rstrip("/").split("/")[-1]} for o in outliers if o.get("url")],
                "instagram", "radar")
    metric = "likes" if radar.get("source", "meta") == "meta" else "views"  # Instagram's free tool shares likes, not views
    db.save_research("radar", {"checked_at": local_now().isoformat(), "outliers": outliers, "metric": metric})
    db.log(f"Competitor radar: {len(outliers)} outliers")


def refresh_history():
    """Weekly: my own reels + views (for best posting times and what's worked)."""
    c = cfg()
    graph = f"https://graph.facebook.com/{c['posting']['graph_api_version']}"
    auth = _ig_auth()
    url = f"{graph}/{env('IG_USER_ID')}/media"
    params = {"fields": "id,caption,timestamp,media_product_type,permalink,media_url", "limit": 50, **auth}
    reels = []
    while url and len(reels) < 120:
        r = requests.get(url, params=params, timeout=60).json()
        if "error" in r:  # e.g. an expired token: say so, instead of "0 reels"
            raise RuntimeError(f"Instagram: {r['error'].get('message', r['error'])}")
        reels +=[m for m in r.get("data", []) if m.get("media_product_type") == "REELS"]
        url, params = r.get("paging", {}).get("next"), {}
    zone = tz()
    by_hour = defaultdict(list)
    for m in reels:
        r = requests.get(f"{graph}/{m['id']}/insights", params={"metric": "views", **auth}, timeout=30)
        if r.ok and r.json().get("data"):
            m["views"] = r.json()["data"][0]["values"][0]["value"]
            hour = datetime.fromisoformat(m["timestamp"].replace("+0000", "+00:00")).astimezone(zone).hour
            by_hour[hour].append(m["views"])
    hours = sorted(({"hour": h, "reels": len(v), "median_views": int(statistics.median(v))}
                    for h, v in by_hour.items() if len(v) >= 3), key=lambda x: x["median_views"], reverse=True)
    n = int(setting("posts_per_day") or 5)
    db.save_research("best_times", {"checked_at": local_now().isoformat(), "hours": hours,
                                    "recommended": sorted(f"{h['hour']:02d}:00" for h in hours[:n])})
    db.save_research("my_reels", {"checked_at": local_now().isoformat(),
                                  "reels": [{k: m.get(k) for k in ("id", "caption", "timestamp", "views", "permalink")}
                                            for m in reels if "views" in m]})
    try:
        refresh_look([m for m in reels if m.get("media_url")][:12])
    except Exception as e:
        db.log(f"Colour reference skipped: {e}")
    db.log(f"History refreshed: {len(reels)} reels, best hours {', '.join(f'{h['hour']:02d}:00' for h in hours[:3])}")


def refresh_look(reels):
    """Learn my colour look from my latest reels, so new reels are graded to match."""
    with tempfile.TemporaryDirectory() as tmp:
        paths = []
        for i, m in enumerate(reels):
            r = requests.get(m["media_url"], timeout=120)
            if r.ok:
                p = Path(tmp) / f"{i}.mp4"
                p.write_bytes(r.content)
                paths.append(p)
        if paths:
            ref = editor.build_reference(paths)
            db.save_research("look", {"checked_at": local_now().isoformat(), "reels": len(paths), **ref})


# --------------------------------------------------------------------------- planning

FALLBACK_TIMES = ["16:00", "11:00", "07:00", "15:00", "13:00", "19:00", "09:00", "21:00", "12:00", "18:00"]


def posting_times():
    """One time per reel per day: your best hours first, topped up with sensible times if you post a lot."""
    if setting("times_mode") == "manual":
        return sorted(setting("post_times") or ["09:00", "12:00", "15:00", "18:00", "21:00"])
    n = int(setting("posts_per_day") or 5)
    best = db.latest_research("best_times")
    ranked = [f"{h['hour']:02d}:00" for h in best["hours"]] if best else []
    times = list(dict.fromkeys(ranked + FALLBACK_TIMES))[:n]
    return sorted(times)


# --------------------------------------------------------------------------- research mix
# Like an investment portfolio: each reel is mainly built on one source of research.
#   instagram = proven on Instagram now (your winners, topic winners, competitor outliers): the safe bet
#   tiktok    = rising on TikTok, not yet big on Instagram: the early-wave bet
#   trends    = news and Google trends that fit the clip: a riskier bet
#   original  = something nobody in the niche is doing, in your own voice; winners become a series: the trend-setter bet
SOURCES = ("instagram", "tiktok", "trends", "original")
SOURCE_LABELS = {"instagram": "📸 Instagram", "tiktok": "🎵 TikTok", "trends": "🔥 News & trends", "original": "✨ Original"}
MIX_FLOOR, MIX_STEP = 10, 10  # rebalancing never drops a source below 10%, and moves 10 points at most a week
BREAKOUT = 3  # a breakout = 3x your usual views

# Starting estimates until your own results take over (needs 4+ reels with results per source):
#   steady = typical views vs your usual reel · breakout = chance one reel does 3x+ your usual
PRIORS = {"instagram": {"steady": 1.0, "breakout": 0.05}, "tiktok": {"steady": 0.9, "breakout": 0.08},
          "trends": {"steady": 0.6, "breakout": 0.10}, "original": {"steady": 0.7, "breakout": 0.12}}


def research_mix():
    mix = {s: int(cfg()["research_mix"].get(s) or 0) for s in SOURCES}
    return mix if sum(mix.values()) > 0 else {s: 100 if s == "instagram" else 0 for s in SOURCES}


def mix_counts(n, mix=None):
    """Split n reels by the mix percentages (largest remainder, so 10 reels at 50/30/20 = 5/3/2)."""
    mix = mix or research_mix()
    total = sum(mix.values())
    quotas = {s: n * mix[s] / total for s in SOURCES}
    counts = {s: int(q) for s, q in quotas.items()}
    for s in sorted(SOURCES, key=lambda s: (-(quotas[s] - counts[s]), SOURCES.index(s)))[: n - sum(counts.values())]:
        counts[s] += 1
    # Every source that's switched on gets at least one reel (when there are enough), so it keeps being tested.
    on = [s for s in SOURCES if mix[s] > 0]
    if n >= len(on):
        for s in on:
            if counts[s] == 0:
                counts[max(SOURCES, key=lambda x: counts[x])] -= 1
                counts[s] = 1
    return counts


def mix_plan(n, recent=40, mix=None):
    """The sources for n reels, each different where possible. Each goes to the source furthest behind its share over
    your last reels, so the mix holds across batches: with 2 reels per clip, trends and original still get their turn."""
    mix, made, order = mix or research_mix(), Counter(), []
    if recent:
        made.update(r["source"] for r in db.q("SELECT source FROM reels WHERE source IS NOT NULL ORDER BY created_at DESC LIMIT ?", recent))
    total = sum(mix.values())
    for _ in range(n):
        count = sum(made.values()) + 1
        s = max((s for s in SOURCES if mix[s]), key=lambda s: (s not in order, count * mix[s] / total - made[s], -SOURCES.index(s)))
        order.append(s)
        made[s] += 1
    return order


def _result_rows(days):
    return db.q("""SELECT r.id, r.source, r.risky, r.series, r.on_screen_text, r.angle, s.views
                   FROM reels r JOIN snapshots s ON s.reel_id = r.id
                   WHERE s.hours = (SELECT MAX(hours) FROM snapshots WHERE reel_id = r.id) AND s.hours >= 48
                   AND r.posted_at >= ?""", (local_now() - timedelta(days=days)).isoformat())


def usual_views():
    """Your usual views per reel: from ReelBot's own trial reels once there are 8+, else your recent reels."""
    views = [r["views"] or 0 for r in _result_rows(3650)]
    if len(views) >= 8:
        return int(statistics.median(views))
    mine = db.latest_research("my_reels")
    if mine and mine.get("reels"):
        return int(statistics.median(r["views"] or 0 for r in mine["reels"]))
    return 10000


def source_results(days=30):
    """Per research source: reels with results, median views (72h, or 48h) and how many broke out (3x usual)."""
    usual = usual_views()
    by = defaultdict(list)
    for r in _result_rows(days):
        by[r["source"] or ("trends" if r["risky"] else "instagram")].append(r["views"] or 0)
    out = {}
    for s, v in by.items():
        med, hits = int(statistics.median(v)), sum(x >= BREAKOUT * usual for x in v)
        # Rebalancing score: views, with extra credit for breakouts (a trend-setter can win on breakouts alone).
        out[s] = {"reels": len(v), "median": med, "breakouts": hits, "score": int(med * (1 + 2 * hits / len(v)))}
    return out


def outlook():
    """What each source tends to do: steady views per reel and chance of a breakout.
    Starts from estimates, blends in your real results as they come in (fully yours after ~8 reels)."""
    usual, res = usual_views(), source_results(days=90)
    out = {}
    for s in SOURCES:
        prior, r = PRIORS[s], res.get(s)
        w = min(r["reels"] / 8, 1) if r else 0
        steady = (1 - w) * prior["steady"] * usual + w * (r["median"] if r else 0)
        rate = (r["breakouts"] + prior["breakout"] * 4) / (r["reels"] + 4) if r else prior["breakout"]
        out[s] = {"steady": int(steady), "breakout": round(rate, 3), "reels": r["reels"] if r else 0,
                  "from_results": bool(r and r["reels"] >= 4)}
    return {"usual": usual, "sources": out}


def rebalance_mix(min_reels=4):
    """Weekly: move up to 10 points from the weakest source to the strongest, never below 10% each."""
    if not setting("mix_auto"):
        return
    res = {s: r for s, r in source_results().items() if r["reels"] >= min_reels}
    mix = research_mix()
    if len(res) < 2:
        db.log("Research mix: not enough results yet to rebalance (needs 4+ reels per source)")
        return
    best = max(res, key=lambda s: res[s]["score"])
    worst = min(res, key=lambda s: res[s]["score"])
    move = min(MIX_STEP, mix[worst] - MIX_FLOOR)
    if best == worst or res[best]["score"] < res[worst]["score"] * 1.2 or move <= 0:
        db.log("Research mix: no clear winner this week, keeping " + " / ".join(f"{mix[s]}%" for s in SOURCES))
        return
    mix[best] += move
    mix[worst] -= move
    for s in SOURCES:
        db.set_setting(f"mix_{s}", mix[s])
    hits = lambda s: f", {res[s]['breakouts']} breakout{'s' if res[s]['breakouts'] != 1 else ''}" if res[s]["breakouts"] else ""
    reason = (f"{SOURCE_LABELS[best]} reels got a median {res[best]['median']:,} views{hits(best)} vs "
              f"{res[worst]['median']:,}{hits(worst)} for {SOURCE_LABELS[worst]}")
    db.save_research("mix_change", {"checked_at": local_now().isoformat(), "mix": mix, "from": worst, "to": best,
                                    "points": move, "reason": reason, "results": res})
    db.log(f"Research mix rebalanced: +{move}% {SOURCE_LABELS[best]}, −{move}% {SOURCE_LABELS[worst]} ({reason})")


def spread_slots(count, start_day=None):
    """Free posting times for reels made from the same clip: never two on the same day."""
    day = start_day or local_now().date()
    slots = []
    for i in range(count):
        slot = next_free_slots(1, day)[0]
        slots.append(slot)
        day = datetime.fromisoformat(slot).date() + timedelta(days=1)
    return slots


def next_free_slots(count, start_day=None):
    """The next posting times that don't already have a reel booked."""
    taken = {r["post_at"] for r in db.q("SELECT post_at FROM reels WHERE status IN ('scheduled','posting','posted')")}
    taken |= {r["recommended_time"] for r in db.q("SELECT recommended_time FROM reels WHERE status IN ('draft','rendering')")}
    times = posting_times()
    day = start_day or local_now().date()
    slots = []
    while len(slots) < count:
        for t in times:
            slot = f"{day}T{t}"
            if slot not in taken and datetime.fromisoformat(slot) > local_now() + timedelta(minutes=10):
                slots.append(slot)
                if len(slots) == count:
                    break
        day += timedelta(days=1)
    return slots


def learnings():
    """What's worked in my own trial reels, from their 72h (or latest) results."""
    rows = db.q("""SELECT r.risky, r.source, r.angle, r.sound_suggestion, r.track, r.virality_score, r.on_screen_text,
                          MAX(s.hours) AS hours, s.views FROM reels r JOIN snapshots s ON s.reel_id = r.id
                   GROUP BY r.id""")
    if not rows:
        return "No ReelBot trial reels with results yet."
    by_angle = defaultdict(list)
    for r in rows:
        by_angle[r["angle"]].append(r["views"] or 0)
    lines = [f"- angle '{a}': {len(v)} reels, median {int(statistics.median(v)):,} views"
             for a, v in sorted(by_angle.items(), key=lambda x: -statistics.median(x[1]))]
    by_source = defaultdict(list)
    for r in rows:
        by_source[r["source"] or ("trends" if r["risky"] else "instagram")].append(r["views"] or 0)
    for src, v in by_source.items():
        lines.append(f"- {src}-led reels: {len(v)}, median {int(statistics.median(v)):,} views")
    best = sorted(rows, key=lambda r: -(r["views"] or 0))[:5]
    worst = sorted(rows, key=lambda r: r["views"] or 0)[:5]
    lines.append("Best: " + " | ".join(f'"{r["on_screen_text"]}" {(r["views"] or 0):,} (predicted {r["virality_score"]})' for r in best))
    lines.append("Worst: " + " | ".join(f'"{r["on_screen_text"]}" {(r["views"] or 0):,} (predicted {r["virality_score"]})' for r in worst))
    return "\n".join(lines)


def build_context(topic, tiktok=None, keywords=None, hunt=None):
    """Everything the planner reads, with an id on every research item ([I3], [T2], [K7]…) so each reel can say
    exactly which creators, reels and searches it took from. Returns (text, refs: id → item)."""
    parts, refs = [], {}

    def ref(prefix, item):
        rid = f"{prefix}{sum(1 for k in refs if k[0] == prefix) + 1}"
        refs[rid] = item
        return f"[{rid}]"

    mine = db.latest_research("my_reels")
    if mine and mine["reels"]:
        ranked = sorted(mine["reels"], key=lambda r: -(r["views"] or 0))
        med = int(statistics.median(r["views"] or 0 for r in ranked))
        def fmt(r):
            hook = (r["caption"] or "").splitlines()[0][:80] if r["caption"] else ""
            tag = ref("M", {"platform": "you", "account": "you", "url": r.get("permalink") or r.get("url"),
                            "views": r["views"], "text": hook})
            return f'- {tag} "{hook}" → {(r["views"] or 0):,} views'
        parts.append(f"MY RECENT REELS (median {med:,} views). Captions usually match the on-screen hook.\n"
                     "Best:\n" + "\n".join(fmt(r) for r in ranked[:12]) + "\nWorst:\n" + "\n".join(fmt(r) for r in ranked[-8:]))
    parts.append("MY REELBOT TRIAL RESULTS:\n" + learnings())
    board = whats_worked()
    if board["reels"]:
        fmt = lambda rows: "; ".join(f'{x["name"]} {x["ratio"]}x ({x["reels"]} reel{"s" if x["reels"] != 1 else ""})' for x in rows[:8]) or "—"
        parts.append(f"WHAT'S WORKED BEFORE (from {board['reels']} posted ReelBot reels; views vs your usual, 1.0x = normal). "
                     "Lean into what's above 1x, avoid what's below, but don't over-trust anything with only 1 reel:\n"
                     f"- Creators/reels borrowed from: {fmt(board['creators'])}\n- Words used: {fmt(board['words'])}\n"
                     f"- Angles: {fmt(board['formats'])}")
    lessons = [r for r in db.q("SELECT on_screen_text, lesson FROM reels WHERE lesson IS NOT NULL ORDER BY posted_at DESC LIMIT 20")
               if not json.loads(r["lesson"]).get("ignored")][:10]
    if lessons:
        parts.append("LESSONS FROM MY POSTED TRIAL REELS (newest first; apply them):\n" + "\n".join(
            f'- "{r["on_screen_text"]}": {json.loads(r["lesson"])["verdict"]}. {json.loads(r["lesson"])["lesson_for_next"]}'
            for r in lessons))
    if topic:
        parts.append(f"TOPIC RESEARCH (#{' #'.join(topic['hashtags'])}, last 60 days, relevant winners):\n" + ("\n".join(
            f'- {ref("I", {"platform": "instagram", "account": w["account"], "url": w["url"], "views": w["views"], "metric": w.get("metric", "views"), "text": w["on_screen_text"] or (w.get("post_caption") or "")[:90], "music": w.get("music")})}'
            f' @{w["account"] or "?"}: ' + (f'caption "{(w["post_caption"] or "")[:90]}" (found on the web, no numbers)' if w.get("via") == "web"
            else (f'on-screen "{w["on_screen_text"]}"' if w["on_screen_text"] else f'caption "{(w.get("post_caption") or "")[:90]}"')
                 + f' → {(w["views"] or 0):,} {w.get("metric", "views")}, sound: {w["music"] or "?"}')
            for w in topic["winners"]) or "(none on topic: don't cite topic winners or formats)"))
        parts.append(f"Trending sounds on these reels: {', '.join(f'{s} ({n})' for s, n in topic['trending_sounds']) or 'none'}."
                     + (f" Share using original audio: {int(topic['original_audio_share'] * 100)}%." if topic.get("original_audio_share") is not None else ""))
        if topic.get("sounds_7d"):
            parts.append(f"Sounds on reels posted in the LAST 7 DAYS ({topic.get('recent_7d', 0)} reels): "
                         + ", ".join(f"{s} ({n} reels)" for s, n in topic["sounds_7d"]))
    if tiktok and tiktok.get("winners"):
        parts.append(f"TIKTOK RESEARCH (#{' #'.join(tiktok['hashtags'])}, last 30 days — TikTok is usually 1–2 weeks ahead of Instagram):\n"
                     + "\n".join(f'- {ref("T", {"platform": "tiktok", "account": w["account"], "url": w["url"], "views": w["views"], "text": w["on_screen_text"] or (w["post_caption"] or "")[:80], "music": w.get("music")})}'
                                  f' @{w["account"]}: on-screen "{w["on_screen_text"] or "(not read)"}", caption "{(w["post_caption"] or "")[:80]}" '
                                  f'→ {(w["views"] or 0):,} views, {(w["shares"] or 0):,} shares, sound: {w["music"]}' for w in tiktok["winners"]))
        if tiktok.get("sounds_7d"):
            parts.append("Sounds RISING on TikTok (used on these hashtags in the last 7 days): "
                         + ", ".join(f"{s} ({n} videos)" for s, n in tiktok["sounds_7d"]))
    if keywords and keywords.get("items"):
        parts.append(f"WHAT PEOPLE SEARCH about this clip's topic (Google/YouTube autocomplete, UK, from: {', '.join(keywords['terms'])}). "
                     "Words people really type: use them in the hook or caption where they fit naturally:\n" + "\n".join(
            f'- {ref("K", {"platform": k["where"], "text": k["search"], "term": k["term"]})} "{k["search"]}" ({k["where"]})'
            for k in keywords["items"]))
    trends = db.latest_research("trends")
    if trends and trends.get("items"):
        parts.append("TRENDING NOW on Google (search term · searches · headline):\n" + "\n".join(
            f'- {ref("G", {"platform": "google", "text": t["term"], "searches": t["searches"], "headline": t["headline"], "url": t["url"], "geo": t["geo"]})}'
            f' {t["term"]} · {t["searches"]} · {t["headline"][:90]}' for t in trends["items"][:30]))
    if hunt and hunt.get("ideas"):
        parts.append(f"TREND TIE-INS (Creatr's trend hunt: ways to link what's trending right now to THIS clip; Trends slider "
                     f"{hunt['share']}%, so lean into these for trends reels, strongest first):\n" + "\n".join(
            f'- {ref("X", {"platform": "news" if (i["ref"] or "").upper().lstrip("[").startswith("N") else "google", "text": i["trend"], "url": (i["source"] or {}).get("url"), "searches": (i["source"] or {}).get("searches"), "headline": (i["source"] or {}).get("headline") or (i["source"] or {}).get("title")})}'
            f' trend "{i["trend"]}" ({i["why_now"]}) · link: {i["link"]} · hook idea: "{i["hook"]}" · fit {i["fit"]}/10 · risk: {i["risk"]}'
            for i in hunt["ideas"]))
    radar = db.latest_research("radar")
    if radar and radar.get("outliers"):
        metric = radar.get("metric", "views")
        parts.append(f"COMPETITOR OUTLIERS (beat their own median {metric}):\n" + "\n".join(
            f'- {ref("C", {"platform": "instagram", "account": o["account"], "url": o.get("url"), "views": o["views"], "metric": metric, "ratio": o["ratio"], "text": o.get("on_screen_text") or o.get("post_caption", "")[:60]})}'
            f' @{o["account"]}: "{o.get("on_screen_text") or o.get("post_caption", "")[:60]}" {o["ratio"]}x, {(o["views"] or 0):,} {metric}'
            for o in radar["outliers"][:12]))
    saved = db.q("SELECT * FROM library WHERE source = 'saved' ORDER BY last_seen DESC LIMIT 15")
    if saved:
        parts.append("REELS THE CREATOR SAVED AS INSPIRATION (strong signal of their taste; adapt, never copy):\n" + "\n".join(
            f'- {ref("S", {"platform": s["platform"], "account": s["creator"], "url": s["url"], "views": s["views"], "text": s["on_screen_text"], "music": s["music"], "note": s["note"]})}'
            f' {s["platform"]} @{s["creator"] or "?"}: on-screen "{s["on_screen_text"] or "(not read)"}", '
            f'{(s["views"] or 0):,} views, sound: {s["music"] or "?"}' + (f' — their note: "{s["note"]}"' if s["note"] else "")
            for s in saved))
    series = series_to_continue()
    if series:
        parts.append("SERIES TO CONTINUE (your Original reels that beat your usual views; make the next part in the same format):\n"
                     + "\n".join(f'- series "{s["series"]}": part {s["next_part"]} next. Best so far: "{s["hook"]}" → {(s["views"] or 0):,} views ({s["angle"]})'
                                  for s in series))
    used = [r["on_screen_text"] for r in db.q("SELECT on_screen_text FROM reels WHERE status != 'rejected'")]
    if used:
        parts.append("HOOKS ALREADY USED on other ReelBot reels (don't repeat them; most aren't posted yet, so they are NOT "
                     "the creator's past winners and are no evidence of anything):\n" + "\n".join(used[-60:]))
    return "\n\n".join(parts), refs


def whats_worked(days=180):
    """Every creator, search word and angle ReelBot borrowed from, scored by how the reels that used them did
    (views vs your usual, from each posted reel's latest results). The free research that gets better over time."""
    usual = usual_views() or 1
    since = (local_now() - timedelta(days=days)).isoformat()
    rows = db.q("""SELECT r.inspirations, r.keywords, r.angle, r.on_screen_text, s.views FROM reels r JOIN snapshots s ON s.reel_id = r.id
                   WHERE s.hours = (SELECT MAX(hours) FROM snapshots WHERE reel_id = r.id) AND r.posted_at >= ?""", since)
    groups = {"creators": defaultdict(list), "words": defaultdict(list), "formats": defaultdict(list)}
    for r in rows:
        hit = ((r["views"] or 0) / usual, r["on_screen_text"], r["views"] or 0)
        for x in json.loads(r["inspirations"] or "[]"):
            if x.get("platform") == "you":
                groups["creators"]["your own reels"].append(hit)
            elif x.get("account"):
                groups["creators"][f"@{x['account']} ({'TikTok' if x.get('platform') == 'tiktok' else 'Instagram'})"].append(hit)
            elif x.get("text"):
                groups["words"][x["text"].lower()].append(hit)
        for k in json.loads(r["keywords"] or "[]"):
            groups["words"][k["word"].lower()].append(hit)
        if r["angle"]:
            groups["formats"][r["angle"]].append(hit)
    out = {"reels": len(rows), "usual": usual}
    for g, items in groups.items():
        out[g] = sorted(({"name": name, "reels": len(h), "ratio": round(statistics.median(x[0] for x in h), 1),
                          "best": max(h, key=lambda x: x[2])[1]} for name, h in items.items()),
                        key=lambda x: (-x["ratio"], -x["reels"]))
    return out


def resolve_refs(plan, refs):
    """Turn the planner's [I3]-style citations into the real creators, reels and searches (dropping any it made up)."""
    clean = lambda r: (r or "").strip().strip("[]").upper()
    insp = [{"ref": clean(x["ref"]), "took": x["took"], **refs[clean(x["ref"])]}
            for x in plan.get("inspirations", []) if clean(x["ref"]) in refs]
    words = [{"word": x["word"], "why": x["why"], "ref": clean(x["ref"]), **refs.get(clean(x["ref"]), {})}
             for x in plan.get("keywords", []) if x.get("word")]
    return insp, words


def series_to_continue(limit=4):
    """Original reels that beat your usual views by 1.5x+: formats worth turning into a series."""
    usual, best = usual_views(), {}
    for r in _result_rows(60):
        if (r["source"] == "original") and (r["views"] or 0) >= 1.5 * usual:
            name = r["series"] or r["on_screen_text"]
            if name not in best or r["views"] > best[name]["views"]:
                best[name] = {"series": name, "hook": r["on_screen_text"], "views": r["views"], "angle": r["angle"]}
    for s in best.values():
        s["next_part"] = db.one("SELECT COUNT(*) n FROM reels WHERE series = ? OR (series IS NULL AND on_screen_text = ?)",
                                s["series"], s["series"])["n"] + 1
    return sorted(best.values(), key=lambda s: -s["views"])[:limit]


MAX_PER_CLIP = 2  # trial reels per clip per 30 days


def actual_score(views, usual=None):
    """Turn real views into the same 0-100 scale as the predicted virality score: 50 = your usual reel,
    each doubling adds 15 (2x = 65, 4x = 80, 8x = 95) and each halving takes 15 off."""
    usual = usual or usual_views() or 1
    if views is None:
        return None
    return max(0, min(100, round(50 + 15 * math.log2(max(views, 1) / usual))))


def clip_allowance(clip_id, day=None):
    """How many more trial reels this clip may get: max 2 per 30 days, and none on a day it already has one."""
    since = (datetime.now(ZoneInfo("UTC")) - timedelta(days=30)).isoformat(timespec="seconds")
    rows = db.q("SELECT COALESCE(post_at, recommended_time) AS t, parent FROM reels WHERE clip_id = ? AND status != 'rejected' "
                "AND created_at >= ?", clip_id, since)
    if day and any(r["t"] and r["t"].startswith(str(day)) for r in rows):
        return 0
    return MAX_PER_CLIP - sum(1 for r in rows if not r["parent"])  # a remake of a posted reel doesn't count (1 per reel)


# --------------------------------------------------------------------------- uploads in batches

def start_batch(batch, combine, expected, library_ids=(), mix=None):
    """Upload page pressed Start: remember what's coming (and how bold to go) so a combined edit waits for every clip."""
    mix = {s: max(0, int((mix or {}).get(s) or 0)) for s in SOURCES} if mix else None
    db.set_setting(f"batch:{batch}", {"combine": bool(combine), "expected": int(expected),
                                      "mix": mix if mix and sum(mix.values()) else None})
    for cid in library_ids:  # clips picked from the library: no re-upload needed
        db.update("clips", cid, batch=batch, combine=1 if combine else 0)
    if library_ids and not expected:
        batch_ready(batch)


_batch_lock = threading.Lock()


def batch_ready(batch):
    """When every clip of a batch is analysed: combine them into one edit, or make reels from each."""
    with _batch_lock:  # two workers can finish the last two clips at the same moment
        _batch_ready(batch)


def _batch_ready(batch):
    info = db.get_setting(f"batch:{batch}") or {}
    clips = db.q("SELECT * FROM clips WHERE batch = ?", batch)
    uploads = [c for c in clips if c["status"] in ("new", "analysing")]
    if uploads or len([c for c in clips if not c["filename"].startswith("Combined:")]) < info.get("expected", 0):
        return  # still waiting for some
    if info.get("done"):
        return
    db.set_setting(f"batch:{batch}", {**info, "done": True})
    mains = [c for c in clips if c["kind"] == "main" and c["status"] != "failed" and not c["filename"].startswith("Combined:")]
    brolls = [c for c in clips if c["kind"] == "broll" and c["status"] != "failed"]
    if info.get("combine") and mains:
        submit("edit clips together", make_combo, batch)
    elif setting("mode") == "review":
        for c in mains:
            submit(f"make reels for {c['filename']}", make_reels, c["id"], None, None, None, info.get("mix"))


def make_combo(batch):
    """Edit a batch's main clips into one (best part of each, in upload order) with its b-roll over the cut,
    then make reels from that edit like any other clip."""
    c = cfg()
    clips = db.q("SELECT * FROM clips WHERE batch = ? ORDER BY created_at", batch)
    mains = [ensure_working_copy(x) for x in clips if x["kind"] == "main" and x["status"] != "failed"
             and not x["filename"].startswith("Combined:")]
    brolls = [ensure_working_copy(x) for x in clips if x["kind"] == "broll" and x["status"] != "failed"]
    each = max(4.0, float(c["clips"]["reel_seconds"]) * 0.75)
    segments = []
    for m in mains:
        if m["keep_look"]:
            segments.append((m["path"], 0.0, min(m["duration"], 60)))
        else:
            start, length, _ = cut(m["path"], each)
            segments.append((m["path"], start, length))
    broll = (brolls[0]["path"], max(0.0, min(1.0, brolls[0]["duration"] - 1.5))) if brolls else None
    out = db.CLIPS_DIR / f"{db.new_id()}_combined.mp4"
    editor.combine(segments, out, broll)
    names = " + ".join(m["filename"] for m in mains) + (f" (b-roll {brolls[0]['filename']})" if brolls else "")
    tags = list(dict.fromkeys(t for m in mains for t in json.loads(m["hashtags"] or "[]")))[:5]
    combo_id = db.new_id()
    db.insert("clips", {
        "id": combo_id, "filename": f"Combined: {names}"[:200], "path": str(out), "kind": "main",
        "duration": editor.probe(out)[0], "batch": batch, "combine": 1,
        "keep_look": 1 if all(m["keep_look"] for m in mains) else 0, "status": "analysed",
        "subject": " → ".join(m["subject"] or m["filename"] for m in mains),
        "description": " / ".join(m["description"] for m in mains if m["description"]) or None,
        "hashtags": json.dumps(tags), "notes": f"Edited together by Creatr from {names}",
        "search_terms": json.dumps(list(dict.fromkeys(t for m in mains for t in json.loads(m["search_terms"] or "[]")))[:3]),
        "broll_silent": 1})
    for m in mains + brolls:
        db.update("clips", m["id"], status="used")
    db.log(f"Edited {len(mains)} clip(s){' + b-roll' if brolls else ''} into one: {names}")
    make_reels(combo_id, mix=(db.get_setting(f"batch:{batch}") or {}).get("mix"))


def cut(path, seconds):
    """Which part of the clip a reel uses: the window with the biggest sound moment. Returns (start, length, reason)."""
    duration, has_audio = editor.probe(path)
    length = min(seconds, duration)
    start = editor.loudest_start(path, duration, length) if has_audio else 0.0
    reason = (f"{start:.1f}s–{start + length:.1f}s of the {duration:.0f}s clip: the window with the biggest "
              "sound moment, so the payoff lands inside the reel" if has_audio
              else f"First {length:.0f}s of the clip (no sound to find the big moment)")
    return start, length, reason


def gather_research(clip, sources, trend_share=0):
    """All the research for one clip, plus a plain record of what ran and what didn't (shown on every reel).
    trend_share = the Trends slider (%): the higher it is, the harder Creatr hunts for trends to tie the clip to."""
    status, tags = [], json.loads(clip["hashtags"] or "[]")
    terms = json.loads(clip["search_terms"] or "[]") or [" ".join((clip["subject"] or "").split()[:4])]

    doing = {"Google trends": "checking Google trends", "Instagram": "researching Instagram", "TikTok": "researching TikTok",
             "Trend hunt": "hunting for trends to tie in", "Google searches": "checking what people search on Google"}

    def attempt(name, fn, *args):
        step(clip["id"], doing.get(name, name))
        try:
            return fn(*args)
        except Exception as e:
            status.append({"source": name, "ok": False, "text": str(e)[:200]})
            db.log(f"{name} research skipped: {e}")
            return None

    trends = attempt("Google trends", google_trends)
    if trends:
        status.append({"source": "Google trends", "ok": True, "text": f"{len(trends.get('items', []))} trending searches (UK + US)"})
    how = lambda r: f" via {', '.join(r['via'])}" if r.get("via") else ""
    topic = attempt("Instagram", research_topic, tags, clip["subject"], 20, terms) if tags else None
    if topic:
        status.append({"source": "Instagram", "ok": True, "text": (
            f"used {len(topic['winners'])} saved reels for #{' #'.join(topic['hashtags'])} (free, no new search)" if topic.get("from_library")
            else f"{topic['found']} reels for #{' #'.join(topic['hashtags'])}{how(topic)}, {len(topic['winners'])} on-topic winners"
            + (f" · didn't work: {'; '.join(topic['problems'])}" if topic.get("problems") else ""))})
    tiktok = None
    if "tiktok" in sources and tags:
        tiktok = attempt("TikTok", research_tiktok, tags, clip["subject"], 15, terms)
        if tiktok:
            status.append({"source": "TikTok", "ok": True, "text": (
                f"used {len(tiktok['winners'])} saved TikToks (free, no new search)" if tiktok.get("from_library")
                else f"{tiktok['found']} videos{how(tiktok)}, {len(tiktok['winners'])} winners")})
    hunt = attempt("Trend hunt", trend_hunt, clip, trend_share) if trend_share > 0 else None
    if hunt and hunt["level"] != "light":
        status.append({"source": "Trend hunt", "ok": True, "text": (
            f"{hunt['level']} (Trends slider {trend_share}%): {len((trends or {}).get('items', [])[:30])} Google trends"
            + (f" + {len(hunt['news'])} stories from this week's news" if hunt["news"] else "")
            + f" → {len(hunt['ideas'])} ways to tie this clip to a trend")})
    elif hunt:
        status.append({"source": "Trend hunt", "ok": True, "text": f"light (Trends slider {trend_share}%): Google's trending searches only. "
                                                                    "Turn Trends up to 25%+ for trend tie-in ideas, 50%+ to search this week's news too"})
    keywords = attempt("Google searches", google_keywords, terms)
    if keywords:
        status.append({"source": "Google searches", "ok": True,
                       "text": f"{len(keywords['items'])} things people search about “{'”, “'.join(keywords['terms'])}”"})
    return topic, tiktok, keywords, status, hunt


def step(clip_id, text):
    """What a clip is doing right now, shown under its progress wheel in the pipeline."""
    db.update("clips", clip_id, step=text)


def make_reels(clip_id, n=None, post_at=None, sources=None, mix=None):
    """make_reels, but if anything goes wrong the clip says where it stopped and why (instead of sitting in the
    pipeline forever)."""
    try:
        _make_reels(clip_id, n, post_at, sources, mix)
    except Exception as e:
        clip = db.one("SELECT status, step FROM clips WHERE id = ?", clip_id)
        if clip and clip["status"] == "making":
            db.update("clips", clip_id, status="failed",
                      notes=f"Stopped while {clip['step'] or 'making reels'}: {str(e)[:250]}")
        raise
    finally:
        step(clip_id, None)


def _make_reels(clip_id, n=None, post_at=None, sources=None, mix=None):
    """Plan + render n reels for one clip. Review mode → drafts; autopilot → scheduled.
    mix = how bold to go for this batch (set on the Upload page); otherwise the mix from Settings."""
    c = cfg()
    clip = db.one("SELECT * FROM clips WHERE id = ?", clip_id)
    n = n or int(setting("reels_per_clip") or 3)
    allowed = clip_allowance(clip_id)
    if allowed <= 0:
        db.update("clips", clip_id, status="used")
        db.log(f"Skipped {clip['filename']}: it already has {MAX_PER_CLIP} trial reels in the last 30 days "
               "(more would look like duplicates to Instagram). Upload new clips or combine it with others.")
        return
    n = min(n, allowed)
    db.update("clips", clip_id, status="making")
    sources = list(sources or (mix_plan(n, recent=0, mix=mix) if mix else mix_plan(n)))
    mix_now = mix or research_mix()
    trend_share = round(100 * (mix_now.get("trends") or 0) / max(sum(mix_now.values()), 1))
    topic, tiktok, keywords, status, hunt = gather_research(clip, sources, trend_share)
    step(clip_id, "finding the best moments in the clip")
    if "tiktok" in sources and not (tiktok and tiktok.get("winners")):  # no TikTok research: lean on Instagram instead
        sources = ["instagram" if s == "tiktok" else s for s in sources]
    library = sorted(p.name for p in db.AUDIO_DIR.glob("*") if p.suffix.lower() in editor.AUDIO_EXTS)
    if clip["keep_look"]:  # you edited and trimmed it yourself: use the whole clip (Instagram's limit is 3 minutes)
        start, length = 0.0, min(clip["duration"], 180)
        cut_reason = f"The whole clip ({length:.0f}s): you edited and trimmed it yourself"
        windows = [start]
    else:
        start, length, cut_reason = cut(clip["path"], c["clips"]["reel_seconds"])
        # Each reel from this clip gets its own part of it, so they aren't near-duplicates of each other.
        windows = editor.loudest_starts(clip["path"], clip["duration"], length, n) if clip["duration"] > length * 1.6 else [start]
    info = {"filename": clip["filename"], "subject": clip["subject"], "notes": clip["notes"], "seconds": clip["duration"],
            "reel_cut": f"{start:.1f}s–{start + length:.1f}s of the clip, so the reel is {length:.0f}s long",
            "creator_description": clip["description"] or ""}
    counts = Counter(sources)
    context, refs = build_context(topic, tiktok, keywords, hunt)
    step(clip_id, "writing the hooks and captions")
    try:
        plans = brain.plan_reels(_frames(clip["path"], 3, start, length), info, n, context, library,
                                 {s: counts.get(s, 0) for s in SOURCES})
    except Exception as e:
        db.update("clips", clip_id, status="failed", notes=f"Planning reels failed: {str(e)[:300]}")
        raise
    mode = setting("mode")
    slots = post_at or spread_slots(len(plans))
    research = research_snapshot(topic, tiktok, keywords, status, hunt)
    for i, (plan, slot) in enumerate(zip(plans, slots)):
        if i < len(windows):
            w_start, motion = windows[i], None
            w_reason = cut_reason if i == 0 else (f"{w_start:.1f}s–{w_start + length:.1f}s: a different part of the clip "
                                                  "from its other reels, so Instagram doesn't see a duplicate")
        else:  # not enough clip for a different part: same moment, different framing
            w_start, motion = windows[0], "push"
            w_reason = cut_reason + " · with a slow push-in so it isn't a duplicate of the other reel"
        step(clip_id, f"editing reel {i + 1} of {len(plans)}")
        save_plan(clip, plan, refs, research, slot=slot, start=w_start, length=length, cut_reason=w_reason, motion=motion,
                  mode=mode, post_at=slot if mode == "autopilot" else None)
    db.update("clips", clip_id, status="used")


def save_plan(clip, plan, refs, research, slot, start, length, cut_reason, motion, mode, post_at=None, parent=None, keep=None):
    """Store one planned reel (with the research it cites) and render it. keep = look settings carried over (remakes)."""
    c = cfg()
    library = sorted(p.name for p in db.AUDIO_DIR.glob("*") if p.suffix.lower() in editor.AUDIO_EXTS)
    trend = plan.get("trend") or ""
    insp, words = resolve_refs(plan, refs)
    reel_id = db.new_id()
    db.insert("reels", {
        "id": reel_id, "clip_id": clip["id"],
        **{k: plan[k] for k in plan if k not in ("track", "positives", "negatives", "trend", "source", "series", "inspirations", "keywords")},
        "series": plan.get("series") or None,
        "source": plan.get("source") or "instagram", "risky": 1 if plan.get("source") == "trends" else 0,
        "positives": json.dumps(plan.get("positives", [])), "negatives": json.dumps(plan.get("negatives", [])),
        "inspirations": json.dumps(insp, ensure_ascii=False), "keywords": json.dumps(words, ensure_ascii=False),
        "trend": trend, "research": json.dumps(research | {"trend": next(
            (t for t in (db.latest_research("trends") or {}).get("items", []) if t["term"].lower() == trend.lower()), None)
            if trend else None}, ensure_ascii=False),
        "track": plan["track"] if plan["track"] in library else "",
        "seconds": length, "start": start, "cut_reason": cut_reason, "motion": motion, "parent": parent,
        "text_style": c["look"].get("text_style", "editorial"),
        "grade": "none" if clip["keep_look"] else c["look"].get("grade", "match"), "recommended_time": slot,
        "post_at": post_at, "mode": mode, "status": "rendering", **(keep or {})})
    render_reel(reel_id)


def research_snapshot(topic, tiktok=None, keywords=None, status=None, hunt=None):
    """The research a batch of reels was planned from, kept with each reel for its "Why this reel" panel."""
    out = {"winners": [], "sounds": [], "sounds_7d": [], "original_share": None, "outliers": [], "hashtags": [],
           "tiktok": [], "tiktok_sounds_7d": [], "searches": [], "status": status or []}
    if tiktok:
        out.update(tiktok=tiktok["winners"][:6], tiktok_sounds_7d=tiktok.get("sounds_7d", [])[:5])
    if topic:
        out.update(winners=topic["winners"][:8], sounds=topic["trending_sounds"][:5], hashtags=topic["hashtags"],
                   sounds_7d=topic.get("sounds_7d", [])[:5], original_share=topic["original_audio_share"])
    if keywords:
        out["searches"] = keywords["items"][:12]
    if hunt and hunt.get("ideas"):
        out["trend_ideas"] = [{k: i[k] for k in ("trend", "why_now", "link", "hook", "fit", "risk")} | {"url": (i["source"] or {}).get("url")}
                              for i in hunt["ideas"][:8]]
        out["trend_level"] = hunt["level"]
    radar = db.latest_research("radar")
    if radar and radar.get("outliers"):
        out["outliers"] = [{k: o.get(k) for k in ("account", "url", "views", "ratio", "on_screen_text", "post_caption")}
                           for o in radar["outliers"][:5]]
    return out


def look_reference():
    ref = db.latest_research("look")
    if ref and ref.get("frames"):
        return ref
    path = DATA / "look_reference.json"
    return json.loads(path.read_text()) if path.exists() else None


def place_text(reel_id, clip, start, length, text, n_lines, size, subject=""):
    """Find where the text is easy to read and blocks nothing: candidate bands are drawn on 3 moments
    of the reel and Claude picks one (using the spots you picked yourself as examples).
    Without Claude, the darkest, calmest band wins. Returns (position, reason, candidate spots)."""
    preview = db.RENDERS_DIR / f"{reel_id}_spots.jpg"
    spots = editor.text_spots(clip, start, length, n_lines, size, k=6, ends=True)
    editor.spots_preview(clip, start, length, spots, n_lines, size, preview)
    if claude_key():
        try:
            picks = db.get_setting("text_picks", [])[-6:]
            examples = ("\nThe creator moved the text themselves on earlier reels; match their taste:\n"
                        + "\n".join(f"- {p}" for p in picks)) if picks else ""
            pick = brain.choose_text_spot(preview.read_bytes(), len(spots), text, examples, subject)
            i = min(max(pick["spot"], 1), len(spots)) - 1
            return spots[i][0], f"Checked {len(spots)} spots on 3 moments of the video: {pick['reason']}", spots
        except Exception as e:
            db.log(f"Text check fell back to the quick measure: {e}")
    best = min(spots, key=lambda s: s[1])
    return best[0], "Darkest, calmest band inside Instagram's safe zone (quick measure only, no AI check)", spots


def render_reel(reel_id):
    c = cfg()
    reel = db.one("SELECT * FROM reels WHERE id = ?", reel_id)
    clip = db.one("SELECT * FROM clips WHERE id = ?", reel["clip_id"])
    db.update("reels", reel_id, status="rendering", error=None)
    try:
        clip = ensure_working_copy(clip)
        duration, has_audio = editor.probe(clip["path"])
        length = min(reel["seconds"] or c["clips"]["reel_seconds"], duration)
        start, cut_reason = reel["start"], reel["cut_reason"]
        if start is None:
            start, length, cut_reason = cut(clip["path"], length)
        look = {**c["look"], "text_style": reel["text_style"], "grade": reel["grade"],
                "adjust": json.loads(reel["adjust"]) if reel["adjust"] else None,
                "layout": reel["text_layout"] or "auto", "text_scale": reel["text_scale"] or 1, "motion": reel["motion"]}
        if look["grade"] == "match":
            look["reference"] = look_reference()
        style = editor.TEXT_STYLES[look["text_style"]]
        text = editor.clean_text(reel["on_screen_text"])
        lines, size = editor.text_lines(text, look)
        n_lines = len(lines)
        pos, text_reason, spots = reel["text_position"], reel["text_reason"], reel["text_spots"]
        if pos is None:
            pos, text_reason, found = place_text(reel_id, clip["path"], start, length, text, n_lines, style["size"],
                                                 clip["subject"] or "")
            spots = json.dumps(found)
        look["text_position"] = pos
        if editor.band_brightness(clip["path"], start, length, pos, n_lines, style["size"]) > 140:
            look["shadow"] = 0.65  # light background behind the text: a stronger soft shadow keeps it readable
        audio = copy.deepcopy(c["audio"])
        if reel["track"]:
            audio.update(mode="mix", track=reel["track"])
        else:
            audio["mode"] = "original"
        broll = None
        if reel["broll"]:
            b = json.loads(reel["broll"])
            bclip = ensure_working_copy(db.one("SELECT * FROM clips WHERE id = ?", b["clip_id"]))
            broll = {**b, "clip": bclip["path"], "silent": bool(bclip["broll_silent"])}
        out = db.RENDERS_DIR / f"{reel_id}.mp4"
        editor.render(clip["path"], out, editor.clean_text(reel["on_screen_text"]), start, length, look, audio, broll)
        editor.extract_frame(out, min(1.5, length / 2), out.with_suffix(".jpg"))  # preview picture
        status = "scheduled" if reel["post_at"] else "draft"
        db.update("reels", reel_id, video_path=str(out), start=start, text_position=pos, status=status,
                  cut_reason=cut_reason, text_reason=text_reason, text_spots=spots)
    except Exception as e:
        db.update("reels", reel_id, status="failed", error=str(e)[:400])
        raise


def autopilot_daily():
    """Every morning, fill tomorrow's slots (your reels-per-day) from clips not used yet, oldest first.
    Autopilot schedules them; review mode leaves them waiting for your OK at their suggested times."""
    n = int(setting("posts_per_day") or 5)
    tomorrow = local_now().date() + timedelta(days=1)
    slots = next_free_slots(n, tomorrow)
    if not slots:
        return
    # Fresh clips first, then clips with room left (max 2 trial reels per clip per 30 days, one a day).
    # Never recycle beyond that: Instagram treats near-identical reels as duplicates.
    clips = [cl for cl in db.q("SELECT * FROM clips WHERE kind = 'main' AND status IN ('analysed', 'used') "
                                "AND (batch IS NULL OR combine = 0 OR filename LIKE 'Combined:%') "
                                "ORDER BY status = 'used', created_at")
             if clip_allowance(cl["id"], tomorrow) > 0][:len(slots)]
    if not clips:
        db.log("Autopilot: no fresh clips left. Upload some new clips (old ones would look like duplicates).")
        return
    if len(clips) < len(slots):
        db.log(f"Autopilot: only {len(clips)} clip(s) can post tomorrow without repeating; upload more for {n} a day")
        slots = slots[:len(clips)]
    planned, sources = len(slots), mix_plan(len(slots))
    split = Counter(sources)
    per_clip = 1
    for clip in clips:
        mine, slots = slots[:per_clip], slots[per_clip:]
        theirs, sources = sources[:len(mine)], sources[len(mine):]
        if mine:
            make_reels(clip["id"], len(mine), post_at=mine, sources=theirs)
    db.log(f"Planned {planned} trial reels for {tomorrow}: "
           + ", ".join(f"{split[s]} {SOURCE_LABELS[s]}" for s in SOURCES if split[s])
           + (" — waiting for your review" if setting("mode") == "review" else ""))


# --------------------------------------------------------------------------- posting + results

def _ig_auth():
    token = env("IG_ACCESS_TOKEN", required=False)
    return {"access_token": token} if token else {}


def approve(reel_id, post_at):
    db.update("reels", reel_id, post_at=post_at, status="scheduled")


def pick_text_spot(reel_id, n):
    """You picked the text spot yourself: re-render there and remember it as an example of your taste."""
    reel = db.one("SELECT * FROM reels WHERE id = ?", reel_id)
    spots = json.loads(reel["text_spots"] or "[]")
    if not 1 <= n <= len(spots):
        return
    picks = db.get_setting("text_picks", [])
    clip = db.one("SELECT subject FROM clips WHERE id = ?", reel["clip_id"])
    picks.append(f"{clip['subject']}: chose box {n} of {len(spots)} (counted from the top)")
    db.set_setting("text_picks", picks[-20:])
    db.update("reels", reel_id, text_position=spots[n - 1][0], text_reason=f"You picked spot {n}", status="rendering")
    submit("re-render", render_reel, reel_id)


TOP_BOTTOM = {"top": 0.16, "bottom": 0.6}


def chat_edit(reel_id, message):
    """You asked for a change in your own words: Claude turns it into edits, then the reel is re-made."""
    reel = db.one("SELECT * FROM reels WHERE id = ?", reel_id)
    history = json.loads(reel["chat"] or "[]")
    current = {"on_screen_text": reel["on_screen_text"], "post_caption": reel["post_caption"],
               "look": reel["grade"], "adjust": json.loads(reel["adjust"] or "{}"),
               "text_position": "top" if (reel["text_position"] or 0.5) < 0.4 else "bottom",
               "text_layout": reel["text_layout"] or "auto", "text_size": reel["text_scale"] or 1,
               "start_seconds": reel["start"], "length_seconds": reel["seconds"]}
    try:
        change = brain.edit_reel(current, message, history[-6:])
    except Exception as e:
        history.append({"you": message, "bot": f"Sorry, I couldn't do that: {e}"})
        db.update("reels", reel_id, chat=json.dumps(history))
        return
    fields = {}
    for key in ("on_screen_text", "post_caption"):
        if change.get(key):
            fields[key] = change[key]
    if change.get("look") in editor.GRADES:
        fields["grade"] = change["look"]
    adjust = {**current["adjust"], **{k: max(-100, min(100, v)) for k, v in (change.get("adjust") or {}).items()
                                      if k in ("brightness", "contrast", "saturation", "warmth")}}
    fields["adjust"] = json.dumps(adjust)
    if change.get("text_layout") == "one_line":
        fields["text_layout"] = "one"
        fields["on_screen_text"] = (fields.get("on_screen_text") or reel["on_screen_text"]).replace(" | ", " ").replace("|", " ")
    elif change.get("text_layout") == "auto":
        fields["text_layout"] = "auto"
        fields["on_screen_text"] = (fields.get("on_screen_text") or reel["on_screen_text"]).replace(" | ", " ").replace("|", " ")
    elif change.get("text_layout") == "split" and change.get("lines"):
        fields["text_layout"] = "custom"
        fields["on_screen_text"] = " | ".join(line.strip() for line in change["lines"] if line.strip())
    scale = {"smaller": 0.85, "bigger": 1.18}.get(change.get("text_size"))
    if scale:
        fields["text_scale"] = round(max(0.6, min(1.8, (reel["text_scale"] or 1) * scale)), 2)
    elif change.get("text_size") == "reset":
        fields["text_scale"] = 1
    if change.get("text_position") in TOP_BOTTOM:
        fields["text_position"], fields["text_reason"] = TOP_BOTTOM[change["text_position"]], f"You asked: “{message}”"
    elif fields.get("on_screen_text"):
        fields["text_position"] = None  # new words: find a spot again
    if change.get("start_seconds") is not None:
        fields["start"], fields["cut_reason"] = max(0.0, float(change["start_seconds"])), f"You asked: “{message}”"
    if change.get("length_seconds"):
        fields["seconds"], fields["cut_reason"] = max(1.0, float(change["length_seconds"])), f"You asked: “{message}”"
        if change.get("start_seconds") is None and reel["start"] is not None:
            fields["start"] = reel["start"]
    history.append({"you": message, "bot": change.get("reply") or "Done."})
    db.update("reels", reel_id, chat=json.dumps(history), status="rendering", **fields)
    render_reel(reel_id)


def rerender_all():
    """Re-make every reel that isn't posted yet (e.g. after a colour fix)."""
    for r in db.q("SELECT id FROM reels WHERE status IN ('draft', 'failed', 'scheduled', 'rendering')"):
        submit("re-make reel", render_reel, r["id"])  # one job each, so both workers share them


def trim(reel_id, start, length, whole=False):
    """You set which part of the clip the reel uses."""
    reel = db.one("SELECT * FROM reels WHERE id = ?", reel_id)
    clip = db.one("SELECT * FROM clips WHERE id = ?", reel["clip_id"])
    duration = clip["duration"] or editor.probe(clip["path"])[0]
    if whole:
        start, length = 0.0, min(duration, 180)
    start = max(0.0, min(float(start), duration - 1))
    length = max(1.0, min(float(length), duration - start, 180))
    db.update("reels", reel_id, start=start, seconds=length, status="rendering",
              cut_reason=f"You chose {start:.1f}s–{start + length:.1f}s of the {duration:.0f}s clip")
    render_reel(reel_id)


def post_now(reel_id):
    db.update("reels", reel_id, post_at=local_now().isoformat(timespec="minutes"), status="scheduled")
    submit("post now", post_due)


def post_due():
    from ..publisher import post_reel
    c = cfg()
    if db.get_setting("posting_paused"):
        return
    due = db.q("SELECT * FROM reels WHERE status = 'scheduled' AND post_at <= ? ORDER BY post_at",
               local_now().isoformat(timespec="minutes"))
    for reel in due[:2]:
        db.update("reels", reel["id"], status="posting")
        try:
            caption = " ".join(x for x in (reel["post_caption"] or reel["on_screen_text"], c["posting"].get("hashtags", "")) if x)
            from .links import public_video_url
            media_id = post_reel(reel["video_path"], caption, c["posting"], video_url=public_video_url(reel["id"]))
            info = requests.get(f"https://graph.facebook.com/{c['posting']['graph_api_version']}/{media_id}",
                                params={"fields": "permalink,is_shared_to_feed", **_ig_auth()}, timeout=30).json()
            db.update("reels", reel["id"], status="posted", media_id=media_id, permalink=info.get("permalink"),
                      posted_at=local_now().isoformat(timespec="minutes"))
            db.log(f"Posted trial reel “{reel['on_screen_text']}”")
            # Safety net: a trial reel shouldn't land on the grid. If Instagram says it did, stop posting.
            if c["posting"].get("trial_reel") and info.get("is_shared_to_feed") is True:
                db.set_setting("posting_paused", f"“{reel['on_screen_text']}” went out as a normal reel, not a trial")
                db.log("⚠️ Posting paused: Instagram posted a reel to your grid instead of as a trial reel")
                return
        except Exception as e:
            db.update("reels", reel["id"], status="failed", error=str(e)[:400])
            db.log(f"✗ Posting failed for “{reel['on_screen_text']}”: {e}")


METRICS = {"views": "views", "reach": "reach", "likes": "likes", "comments": "comments",
           "saved": "saved", "shares": "shares", "avg_watch_ms": "ig_reels_avg_watch_time"}


def fetch_insights(media_id):
    graph = f"https://graph.facebook.com/{cfg()['posting']['graph_api_version']}"
    out = {}
    for col, metric in METRICS.items():  # one by one: Meta rejects the whole call if one metric isn't supported
        r = requests.get(f"{graph}/{media_id}/insights", params={"metric": metric, **_ig_auth()}, timeout=30)
        if r.ok and r.json().get("data"):
            out[col] = r.json()["data"][0]["values"][0]["value"]
    return out


def snapshots_due():
    """Record each posted reel's results at 24h, 48h and 72h."""
    for reel in db.q("SELECT * FROM reels WHERE status = 'posted' AND media_id IS NOT NULL"):
        posted = datetime.fromisoformat(reel["posted_at"])
        have = {s["hours"] for s in db.q("SELECT hours FROM snapshots WHERE reel_id = ?", reel["id"])}
        for h in (24, 48, 72):
            if h not in have and local_now() >= posted + timedelta(hours=h):
                stats = fetch_insights(reel["media_id"])
                db.insert("snapshots", {"reel_id": reel["id"], "hours": h, "taken_at": db.now(), **stats})
                db.log(f"{h}h results for “{reel['on_screen_text']}”: {(stats.get('views') or 0):,} views")
                if h == 72:
                    submit("learn from results", review_reel, reel["id"])
                break  # one per reel per pass is plenty


# --------------------------------------------------------------------------- learning from results
# After 72h (or when you press "Review now") Claude reads a posted reel's numbers: what worked, what didn't, and one
# tweak to test. The lesson feeds every future plan; "Remake with this tweak" makes a new draft of the same clip.

def review_reel(reel_id):
    reel = db.one("SELECT r.*, c.duration AS clip_seconds FROM reels r JOIN clips c ON c.id = r.clip_id WHERE r.id = ?", reel_id)
    snaps = db.q("SELECT * FROM snapshots WHERE reel_id = ? ORDER BY hours", reel_id)
    if not reel or not snaps:
        return None
    results = {s["hours"]: {k: s[k] for k in ("views", "reach", "likes", "comments", "saved", "shares", "avg_watch_ms")
                            if s[k] is not None} for s in snaps}
    info = {k: reel[k] for k in ("on_screen_text", "post_caption", "angle", "source", "trend", "series", "sound_suggestion",
                                 "track", "grade", "text_layout", "motion", "virality_score", "start", "seconds")}
    info["start"], info["seconds"] = info["start"] or 0.0, info["seconds"] or 0.0
    info["predicted"] = f"{reel['virality_score']}/100 (50 = a typical reel)"
    info["inspired_by"] = [f"{x.get('account') or x.get('text')} ({x['took']})" for x in json.loads(reel["inspirations"] or "[]")]
    others = [r for r in _result_rows(90) if r["id"] != reel_id]
    peers = ("Other ReelBot trial reels for comparison: " + "; ".join(
        f'"{r["on_screen_text"]}" ({r["source"]}) {(r["views"] or 0):,} views' for r in others[:10])) if others else ""
    mine = (db.latest_research("my_reels") or {}).get("reels") or []
    best = sorted(mine, key=lambda m: -(m.get("views") or 0))[:10]
    winners = ("THE CREATOR'S BEST REELS (caption → views), to compare against:\n" + "\n".join(
        f'- "{(m.get("caption") or "").splitlines()[0][:100] if m.get("caption") else "(no caption)"}" → {(m["views"] or 0):,}' for m in best)) if best else ""
    lesson = brain.review_result(info, results, usual_views(), reel["clip_seconds"] or reel["seconds"] or 8, peers, winners)
    lesson["new_start"] = max(0.0, min(lesson["new_start"], (reel["clip_seconds"] or 0) - 1))
    lesson["new_length"] = max(3.0, min(lesson["new_length"] or reel["seconds"] or 8, 180))
    lesson["reviewed_at"] = local_now().isoformat(timespec="minutes")
    lesson["hours"] = max(results)
    db.update("reels", reel_id, lesson=json.dumps(lesson, ensure_ascii=False))
    db.log(f"Learned from “{reel['on_screen_text']}”: {lesson['headline']}")
    return lesson


MAX_VERSIONS = 5  # a reel and its remakes: v1 → v2 → … → v5


def versions(reel_id):
    """The whole remake chain a reel belongs to, first version first: [v1, v2, …] (rejected remakes left out)."""
    reel = db.one("SELECT * FROM reels WHERE id = ?", reel_id)
    while reel and reel["parent"]:
        up = db.one("SELECT * FROM reels WHERE id = ?", reel["parent"])
        if not up:
            break
        reel = up
    chain = []
    while reel:
        chain.append(reel)
        reel = db.one("SELECT * FROM reels WHERE parent = ? AND status != 'rejected' ORDER BY created_at LIMIT 1", reel["id"])
    return chain


def remake_allowed(reel_id):
    """Each posted reel can be remade once (on top of the 2-per-clip limit), and a remake can be remade again,
    up to MAX_VERSIONS in a chain. Returns (ok, reason)."""
    if db.one("SELECT id FROM reels WHERE parent = ? AND status != 'rejected'", reel_id):
        return False, "already remade. Reject that remake to try a different one"
    if len(versions(reel_id)) >= MAX_VERSIONS:
        return False, f"this reel has had {MAX_VERSIONS} versions already, so upload fresh clips for this idea"
    return True, ""


def remake(reel_id):
    """Run a remake, keeping the reel's card up to date: "working" while it runs, the reason if it fails."""
    try:
        _remake(reel_id)
        db.update("reels", reel_id, remake_note=None)
    except Exception as e:
        db.update("reels", reel_id, remake_note=f"failed: {str(e)[:200]}")
        raise


def _remake(reel_id):
    """A new draft of a posted reel's clip with the lesson applied: new hook, and a different part or a push-in."""
    ok, why = remake_allowed(reel_id)
    if not ok:
        raise RuntimeError(why)
    reel = db.one("SELECT * FROM reels WHERE id = ?", reel_id)
    lesson = json.loads(reel["lesson"] or "null") or review_reel(reel_id)
    if not lesson:
        raise RuntimeError("no results to learn from yet")
    clip = db.one("SELECT * FROM clips WHERE id = ?", reel["clip_id"])
    if not clip or not Path(clip["path"]).exists():
        raise RuntimeError("the original clip isn't on the server any more (it was deleted), so there's nothing to re-cut")
    clip = ensure_working_copy(clip)
    start = lesson["new_start"]
    length = min(lesson["new_length"], max(1.0, clip["duration"] - start))
    old_start, old_len = reel["start"] or 0.0, reel["seconds"] or length
    overlap = max(0.0, min(start + length, old_start + old_len) - max(start, old_start)) / max(length, 0.1)
    motion = "push" if overlap > 0.5 and reel["motion"] != "push" else None  # mostly the same moment: reframe it
    cut_reason = (f"{start:.1f}s–{start + length:.1f}s of the clip, from the lesson: {lesson['tweak']}"
                  + (" · with a slow push-in so it isn't a duplicate of the first version" if motion else ""))
    topic, tiktok, keywords, status, _ = gather_research(clip, [reel["source"] or "instagram"])
    context, refs = build_context(topic, tiktok, keywords)
    info = {"filename": clip["filename"], "subject": clip["subject"], "notes": clip["notes"], "seconds": clip["duration"],
            "reel_cut": f"{start:.1f}s–{start + length:.1f}s of the clip, so the reel is {length:.0f}s long",
            "creator_description": clip["description"] or ""}
    chain = versions(reel_id)
    history = []
    for n, v in enumerate(chain, 1):
        snap = db.one("SELECT views FROM snapshots WHERE reel_id = ? ORDER BY hours DESC LIMIT 1", v["id"])
        history.append({"version": n, "hook": v["on_screen_text"], "caption": v["post_caption"], "angle": v["angle"],
                        "views": snap["views"] if snap else None,
                        "lesson": (json.loads(v["lesson"]) or {}).get("headline") if v["lesson"] else None})
    brief = {"version_now": len(chain) + 1, "earlier_versions": history,
             "lesson": {k: lesson[k] for k in ("verdict", "headline", "worked", "didnt", "tweak", "change")},
             "rule": "Every earlier version's hook is used: write a clearly new one. Build on what the best version did."}
    library = sorted(p.name for p in db.AUDIO_DIR.glob("*") if p.suffix.lower() in editor.AUDIO_EXTS)
    plan = brain.plan_reels(_frames(clip["path"], 3, start, length), info, 1, context, library,
                            {reel["source"] or "instagram": 1}, remake=brief)[0]
    booked = {(r["t"] or "")[:10] for r in db.q(
        "SELECT COALESCE(posted_at, post_at, recommended_time) t FROM reels WHERE clip_id = ? AND status != 'rejected'", clip["id"])}
    slot = spread_slots(1)[0]
    while slot[:10] in booked:  # never two reels of a clip on one day
        slot = spread_slots(1, datetime.fromisoformat(slot).date() + timedelta(days=1))[0]
    research = research_snapshot(topic, tiktok, keywords, status) | {"remake_of": {"id": reel_id, "hook": reel["on_screen_text"],
                                                                                  "tweak": lesson["tweak"]}}
    save_plan(clip, plan, refs, research, slot=slot, start=start, length=length, cut_reason=cut_reason, motion=motion,
              mode="review", parent=reel_id, keep={k: reel[k] for k in ("grade", "adjust", "text_layout", "text_scale")})
    db.log(f"Remade “{reel['on_screen_text']}” → “{plan['on_screen_text']}” (draft, in Review)")


# --------------------------------------------------------------------------- clock

def _due_daily(key, hour, minute=0, weekday=None):
    now = local_now()
    if weekday is not None and now.weekday() != weekday:
        return False
    target = now.replace(hour=hour, minute=minute)
    last = db.get_setting("last_" + key)
    if now >= target and (not last or last < str(now.date())):
        db.set_setting("last_" + key, str(now.date()))
        return True
    return False


def _clock():
    tick = 0
    while True:
        try:
            post_due()
            if tick % 15 == 0:
                snapshots_due()
            if _due_daily("autopilot", 6, 0):
                submit("autopilot daily plan", autopilot_daily)
            if _due_daily("history", 5, 0, weekday=0) or (tick == 0 and not db.latest_research("best_times")):
                submit("refresh history", refresh_history)
            if _due_daily("rebalance", 5, 45, weekday=0):
                submit("rebalance research mix", rebalance_mix)
            if _due_daily("radar", 5, 30, weekday=0) and (cfg()["radar"].get("source") != "apify" or env("APIFY_TOKEN", required=False)):
                submit("competitor radar", run_radar)
        except Exception as e:
            db.log(f"✗ clock: {e}")
        tick += 1
        time.sleep(60)


def _resume():
    """The task queue lives in memory: after a restart, pick up the work it lost."""
    for c in db.q("SELECT * FROM clips WHERE status IN ('new', 'analysing')"):
        submit(f"analyse {c['filename']}", analyse_clip, c["id"], c["notes"] != "kind set by you")
    for c in db.q("SELECT * FROM clips WHERE status = 'making'"):
        db.update("clips", c["id"], status="failed", notes="Making reels was interrupted by a restart: make them again")
    for r in db.q("SELECT id FROM reels WHERE status = 'rendering'"):
        submit("re-render", render_reel, r["id"])


def start():
    _resume()
    for _ in range(int(os.environ.get("REELBOT_WORKERS", "2"))):  # two reels at once
        threading.Thread(target=_worker, daemon=True).start()
    threading.Thread(target=_clock, daemon=True).start()
