"""ReelBot's engine: analyse clips, research, make reels, post on time and track results.

Heavy work (video, AI) goes through one background worker so nothing runs twice at once.
A scheduler thread handles the clock: posting, 24/48/72h results, daily autopilot, weekly research.
"""

import copy
import json
import math
import queue
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
from ..settings import DATA, env, load_config
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


def add_clip(path, filename, kind=None, description=""):
    clip_id = db.new_id()
    duration, _ = editor.probe(path)
    db.insert("clips", {"id": clip_id, "filename": filename, "path": str(path), "duration": duration,
                        "description": description.strip() or None,
                        "kind": kind or "main", "notes": "kind set by you" if kind else "",
                        "broll_silent": 1 if setting("broll_silent") else 0})
    submit(f"analyse {filename}", analyse_clip, clip_id, kind is None)
    return clip_id


def analyse_clip(clip_id, decide_kind=True, make_after=True):
    clip = db.one("SELECT * FROM clips WHERE id = ?", clip_id)
    db.update("clips", clip_id, status="analysing")
    duration, has_audio = editor.probe(clip["path"])
    loud = editor.loudest_start(clip["path"], duration, min(8, duration)) + 1.0 if has_audio else 0.0
    try:
        info = brain.analyse_clip(_frames(clip["path"], 4), duration, has_audio, loud, cfg()["niche"], clip["description"] or "")
    except Exception as e:  # don't leave it "analysing" forever
        db.update("clips", clip_id, status="failed", notes=f"Analysis failed: {str(e)[:300]}")
        raise
    fields = {"subject": info["subject"], "hashtags": json.dumps(info["hashtags"]), "status": "analysed",
              "notes": f"{info['mood']} · {info['highlight']}"}
    if decide_kind:
        fields["kind"] = info["kind"]
        fields["notes"] += f" · {info['kind']}: {info['kind_reason']}"
    db.update("clips", clip_id, **fields)
    db.log(f"Analysed {clip['filename']}: {info['subject']} ({fields.get('kind', clip['kind'])})")
    if make_after and fields.get("kind", clip["kind"]) == "main" and setting("mode") == "review":
        submit(f"make reels for {clip['filename']}", make_reels, clip_id)


# --------------------------------------------------------------------------- research

APIFY_HASHTAG = "https://api.apify.com/v2/acts/apify~instagram-hashtag-scraper/run-sync-get-dataset-items"


def _apify_headers():
    token = env("APIFY_TOKEN", required=False)
    return {"Authorization": f"Bearer {token}"} if token else {}


def research_topic(hashtags, subject, per_tag=40):
    """Top recent reels for these hashtags: views, on-screen text, sounds. Cached for 3 days."""
    tags = sorted({h.lstrip("#").lower() for h in hashtags})[:5]
    cached = db.latest_research("topic:" + ",".join(tags))
    if cached and datetime.fromisoformat(cached["checked_at"]) > local_now() - timedelta(days=3):
        return cached
    resp = requests.post(APIFY_HASHTAG, json={"hashtags": tags, "resultsType": "reels", "resultsLimit": per_tag},
                         headers=_apify_headers(), timeout=900)
    resp.raise_for_status()
    cutoff = time.time() - 60 * 86400
    reels = [r for r in (competitors.apify_reel(i) for i in resp.json()) if r and r["taken_at"] >= cutoff]
    reels.sort(key=lambda r: r["views"], reverse=True)
    top = reels[:12]
    for r in top:
        r["frame_bytes"] = vision.gather_frames(r.get("video"), r.get("thumbnail"))[:2]
    reads = {x["code"]: x for x in brain.read_reels(top, subject)} if top else {}
    winners = []
    for r in top:
        read = reads.get(r["code"], {})
        if read.get("relevant", True):
            winners.append({k: r.get(k) for k in ("code", "url", "account", "views", "likes", "music", "post_caption")}
                           | {"on_screen_text": read.get("on_screen_text", "")})
    sounds = Counter(r["music"] for r in reels[:30] if r.get("music") and r["music"] != "original audio")
    week = time.time() - 7 * 86400
    sounds_7d = Counter(r["music"] for r in reels if r["taken_at"] >= week and r.get("music") and r["music"] != "original audio")
    original = sum(1 for r in reels[:30] if r.get("music") == "original audio")
    result = {"checked_at": local_now().isoformat(), "hashtags": tags, "subject": subject,
              "found": len(reels), "winners": winners, "trending_sounds": sounds.most_common(10),
              "sounds_7d": sounds_7d.most_common(10), "recent_7d": sum(1 for r in reels if r["taken_at"] >= week),
              "original_audio_share": round(original / max(len(reels[:30]), 1), 2)}
    db.save_research("topic:" + ",".join(tags), result)
    db.save_research("topic", result)
    db.log(f"Researched #{' #'.join(tags)}: {len(winners)} relevant winners")
    return result


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


def research_tiktok(hashtags, subject, per_tag=30):
    """Top TikToks for these hashtags in the last 30 days: views, shares, text and the sounds rising. Cached 3 days."""
    tags = sorted({h.lstrip("#").lower() for h in hashtags})[:4]
    if not tags:
        return None
    key = "tiktok:" + ",".join(tags)
    cached = db.latest_research(key)
    if cached and datetime.fromisoformat(cached["checked_at"]) > local_now() - timedelta(days=3):
        return cached
    resp = requests.post(APIFY_TIKTOK, headers=_apify_headers(), timeout=900, json={
        "hashtags": tags, "resultsPerPage": per_tag, "shouldDownloadVideos": False, "shouldDownloadCovers": False,
        "shouldDownloadSubtitles": False, "shouldDownloadSlideshowImages": False})
    resp.raise_for_status()
    cutoff, week = time.time() - 30 * 86400, time.time() - 7 * 86400
    seen, videos = set(), []
    for v in (_tiktok_video(i) for i in resp.json()):
        if v and v["taken_at"] >= cutoff and v["code"] not in seen:
            seen.add(v["code"])
            videos.append(v)
    videos.sort(key=lambda v: v["views"], reverse=True)
    top = videos[:12]
    for v in top:
        v["frame_bytes"] = vision.gather_frames(None, v.get("thumbnail"))[:1]
    reads = {}
    if any(v["frame_bytes"] for v in top):
        reads = {x["code"]: x for x in brain.read_reels([v for v in top if v["frame_bytes"]], subject)}
    winners = [{k: v.get(k) for k in ("code", "url", "account", "views", "likes", "shares", "music", "post_caption")}
               | {"on_screen_text": reads.get(v["code"], {}).get("on_screen_text", "")}
               for v in top if reads.get(v["code"], {}).get("relevant", True)]
    sounds = lambda vs: Counter(v["music"] for v in vs if v["music"] not in ("original audio", "?")).most_common(8)
    result = {"checked_at": local_now().isoformat(), "hashtags": tags, "subject": subject, "found": len(videos),
              "winners": winners, "sounds": sounds(videos), "sounds_7d": sounds([v for v in videos if v["taken_at"] >= week]),
              "original_audio_share": round(sum(v["music"] == "original audio" for v in videos[:30]) / max(len(videos[:30]), 1), 2)}
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


def run_radar():
    """Weekly: competitor reels that beat their own normal views, with their on-screen text."""
    c = cfg()
    outliers = competitors.run(c["competitors"], c["radar"])
    db.save_research("radar", {"checked_at": local_now().isoformat(), "outliers": outliers})
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


def mix_plan(n):
    """The sources for n reels, interleaved so each clip gets a spread (ig, tiktok, trends, ig, …)."""
    left, order = mix_counts(n), []
    while len(order) < n:
        for s in SOURCES:
            if left[s]:
                order.append(s)
                left[s] -= 1
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
    lines.append("Best: " + " | ".join(f'"{r["on_screen_text"]}" {r["views"]:,} (predicted {r["virality_score"]})' for r in best))
    lines.append("Worst: " + " | ".join(f'"{r["on_screen_text"]}" {r["views"]:,} (predicted {r["virality_score"]})' for r in worst))
    return "\n".join(lines)


def build_context(topic, tiktok=None):
    parts = []
    mine = db.latest_research("my_reels")
    if mine and mine["reels"]:
        ranked = sorted(mine["reels"], key=lambda r: -(r["views"] or 0))
        med = int(statistics.median(r["views"] for r in ranked))
        fmt = lambda r: f'- "{(r["caption"] or "").splitlines()[0][:80]}" → {r["views"]:,} views'
        parts.append(f"MY RECENT REELS (median {med:,} views). Captions usually match the on-screen hook.\n"
                     "Best:\n" + "\n".join(fmt(r) for r in ranked[:12]) + "\nWorst:\n" + "\n".join(fmt(r) for r in ranked[-8:]))
    parts.append("MY REELBOT TRIAL RESULTS:\n" + learnings())
    if topic:
        parts.append(f"TOPIC RESEARCH (#{' #'.join(topic['hashtags'])}, last 60 days, relevant winners):\n" + "\n".join(
            f'- @{w["account"]}: on-screen "{w["on_screen_text"] or "(no text)"}" → {w["views"]:,} views, sound: {w["music"] or "?"}'
            for w in topic["winners"]))
        parts.append(f"Trending sounds on these reels: {', '.join(f'{s} ({n})' for s, n in topic['trending_sounds']) or 'none'}."
                     f" Share using original audio: {int(topic['original_audio_share'] * 100)}%.")
        if topic.get("sounds_7d"):
            parts.append(f"Sounds on reels posted in the LAST 7 DAYS ({topic.get('recent_7d', 0)} reels): "
                         + ", ".join(f"{s} ({n} reels)" for s, n in topic["sounds_7d"]))
    if tiktok and tiktok.get("winners"):
        parts.append(f"TIKTOK RESEARCH (#{' #'.join(tiktok['hashtags'])}, last 30 days — TikTok is usually 1–2 weeks ahead of Instagram):\n"
                     + "\n".join(f'- @{w["account"]}: on-screen "{w["on_screen_text"] or "(not read)"}", caption "{(w["post_caption"] or "")[:80]}" '
                                  f'→ {w["views"]:,} views, {w["shares"]:,} shares, sound: {w["music"]}' for w in tiktok["winners"]))
        if tiktok.get("sounds_7d"):
            parts.append("Sounds RISING on TikTok (used on these hashtags in the last 7 days): "
                         + ", ".join(f"{s} ({n} videos)" for s, n in tiktok["sounds_7d"]))
    trends = db.latest_research("trends")
    if trends and trends.get("items"):
        parts.append("TRENDING NOW on Google (search term · searches · headline):\n" + "\n".join(
            f'- {t["term"]} · {t["searches"]} · {t["headline"][:90]}' for t in trends["items"][:30]))
    radar = db.latest_research("radar")
    if radar and radar.get("outliers"):
        parts.append("COMPETITOR OUTLIERS (beat their own median):\n" + "\n".join(
            f'- @{o["account"]}: "{o.get("on_screen_text") or o.get("post_caption", "")[:60]}" {o["ratio"]}x, {o["views"]:,} views'
            for o in radar["outliers"][:12]))
    series = series_to_continue()
    if series:
        parts.append("SERIES TO CONTINUE (your Original reels that beat your usual views; make the next part in the same format):\n"
                     + "\n".join(f'- series "{s["series"]}": part {s["next_part"]} next. Best so far: "{s["hook"]}" → {s["views"]:,} views ({s["angle"]})'
                                  for s in series))
    used = [r["on_screen_text"] for r in db.q("SELECT on_screen_text FROM reels WHERE status != 'rejected'")]
    if used:
        parts.append("HOOKS ALREADY USED (don't repeat):\n" + "\n".join(used[-60:]))
    return "\n\n".join(parts)


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


def make_reels(clip_id, n=None, post_at=None, sources=None):
    """Plan + render n reels for one clip. Review mode → drafts; autopilot → scheduled."""
    c = cfg()
    clip = db.one("SELECT * FROM clips WHERE id = ?", clip_id)
    n = n or int(setting("reels_per_clip") or 3)
    db.update("clips", clip_id, status="making")
    try:
        google_trends()
    except Exception as e:
        db.log(f"Google trends skipped: {e}")
    topic = None
    if clip["hashtags"] and env("APIFY_TOKEN", required=False) is not None:
        try:
            topic = research_topic(json.loads(clip["hashtags"]), clip["subject"])
        except Exception as e:
            db.log(f"Topic research skipped: {e}")
    sources = list(sources or mix_plan(n))
    tiktok = None
    if "tiktok" in sources:
        try:
            tiktok = research_tiktok(json.loads(clip["hashtags"] or "[]"), clip["subject"])
        except Exception as e:
            db.log(f"TikTok research skipped: {e}")
        if not tiktok or not tiktok.get("winners"):  # no TikTok research: those reels lean on Instagram instead
            sources = ["instagram" if s == "tiktok" else s for s in sources]
    library = sorted(p.name for p in db.AUDIO_DIR.glob("*") if p.suffix.lower() in editor.AUDIO_EXTS)
    info = {"filename": clip["filename"], "subject": clip["subject"], "notes": clip["notes"], "seconds": clip["duration"],
            "creator_description": clip["description"] or ""}
    counts = Counter(sources)
    try:
        plans = brain.plan_reels(_frames(clip["path"], 3), info, n, build_context(topic, tiktok), library,
                                 {s: counts.get(s, 0) for s in SOURCES})
    except Exception as e:
        db.update("clips", clip_id, status="failed", notes=f"Planning reels failed: {str(e)[:300]}")
        raise
    mode = setting("mode")
    slots = post_at or next_free_slots(len(plans))
    research = research_snapshot(topic, tiktok)
    for plan, slot in zip(plans, slots):
        reel_id = db.new_id()
        trend = plan.get("trend") or ""
        db.insert("reels", {
            "id": reel_id, "clip_id": clip_id,
            **{k: plan[k] for k in plan if k not in ("track", "positives", "negatives", "trend", "source", "series")},
            "series": plan.get("series") or None,
            "source": plan.get("source") or "instagram", "risky": 1 if plan.get("source") == "trends" else 0,
            "positives": json.dumps(plan.get("positives", [])), "negatives": json.dumps(plan.get("negatives", [])),
            "trend": trend, "research": json.dumps(research | {"trend": next(
                (t for t in (db.latest_research("trends") or {}).get("items", []) if t["term"].lower() == trend.lower()), None)
                if trend else None}, ensure_ascii=False),
            "track": plan["track"] if plan["track"] in library else "",
            "seconds": c["clips"]["reel_seconds"], "text_style": c["look"].get("text_style", "editorial"),
            "grade": c["look"].get("grade", "match"), "recommended_time": slot,
            "post_at": slot if mode == "autopilot" else None, "mode": mode, "status": "rendering"})
        render_reel(reel_id)
    db.update("clips", clip_id, status="used")


def research_snapshot(topic, tiktok=None):
    """The research a batch of reels was planned from, kept with each reel for its "Why this reel" panel."""
    out = {"winners": [], "sounds": [], "sounds_7d": [], "original_share": None, "outliers": [], "hashtags": [],
           "tiktok": [], "tiktok_sounds_7d": []}
    if tiktok:
        out.update(tiktok=tiktok["winners"][:6], tiktok_sounds_7d=tiktok.get("sounds_7d", [])[:5])
    if topic:
        out.update(winners=topic["winners"][:8], sounds=topic["trending_sounds"][:5], hashtags=topic["hashtags"],
                   sounds_7d=topic.get("sounds_7d", [])[:5], original_share=topic["original_audio_share"])
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


def place_text(reel_id, clip, start, length, text, n_lines, size):
    """Find where the text is easy to read and blocks nothing: candidate bands are drawn on 3 moments
    of the reel and Claude picks one (using the spots you picked yourself as examples).
    Without Claude, the darkest, calmest band wins. Returns (position, reason, candidate spots)."""
    preview = db.RENDERS_DIR / f"{reel_id}_spots.jpg"
    spots = editor.text_spots(clip, start, length, n_lines, size, k=7, spread=True)
    editor.spots_preview(clip, start, length, spots, n_lines, size, preview)
    if env("ANTHROPIC_API_KEY", required=False):
        try:
            picks = db.get_setting("text_picks", [])[-6:]
            examples = ("\nThe creator moved the text themselves on earlier reels; match their taste:\n"
                        + "\n".join(f"- {p}" for p in picks)) if picks else ""
            pick = brain.choose_text_spot(preview.read_bytes(), len(spots), text, examples)
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
        duration, has_audio = editor.probe(clip["path"])
        length = min(reel["seconds"] or c["clips"]["reel_seconds"], duration)
        start, cut_reason = reel["start"], reel["cut_reason"]
        if start is None:
            start = editor.loudest_start(clip["path"], duration, length) if has_audio else 0.0
            cut_reason = (f"{start:.1f}s–{start + length:.1f}s of the {duration:.0f}s clip: the window with the biggest "
                          "sound moment, so the payoff lands inside the reel" if has_audio
                          else f"First {length:.0f}s of the clip (no sound to find the big moment)")
        look = {**c["look"], "text_style": reel["text_style"], "grade": reel["grade"]}
        if look["grade"] == "match":
            look["reference"] = look_reference()
        style = editor.TEXT_STYLES[look["text_style"]]
        text = editor.clean_text(reel["on_screen_text"])
        n_lines = len(editor.textwrap.wrap(text, style["wrap"]))
        pos, text_reason, spots = reel["text_position"], reel["text_reason"], reel["text_spots"]
        if pos is None:
            pos, text_reason, found = place_text(reel_id, clip["path"], start, length, text, n_lines, style["size"])
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
            bclip = db.one("SELECT * FROM clips WHERE id = ?", b["clip_id"])
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
    clips = db.q("SELECT * FROM clips WHERE kind = 'main' AND status IN ('analysed') ORDER BY created_at")
    if not clips:  # nothing new: reuse past clips with fresh hooks
        clips = db.q("SELECT * FROM clips WHERE kind = 'main' AND status = 'used' ORDER BY RANDOM() LIMIT 3")
    if not clips:
        db.log("Autopilot: no clips to use. Upload some main clips.")
        return
    planned, sources = len(slots), mix_plan(len(slots))
    split = mix_counts(planned)
    per_clip = math.ceil(len(slots) / len(clips))
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


def post_now(reel_id):
    db.update("reels", reel_id, post_at=local_now().isoformat(timespec="minutes"), status="scheduled")
    submit("post now", post_due)


def post_due():
    from ..publisher import post_reel
    c = cfg()
    due = db.q("SELECT * FROM reels WHERE status = 'scheduled' AND post_at <= ? ORDER BY post_at",
               local_now().isoformat(timespec="minutes"))
    for reel in due[:2]:
        db.update("reels", reel["id"], status="posting")
        try:
            caption = " ".join(x for x in (reel["post_caption"] or reel["on_screen_text"], c["posting"].get("hashtags", "")) if x)
            media_id = post_reel(reel["video_path"], caption, c["posting"])
            link = requests.get(f"https://graph.facebook.com/{c['posting']['graph_api_version']}/{media_id}",
                                params={"fields": "permalink", **_ig_auth()}, timeout=30).json().get("permalink")
            db.update("reels", reel["id"], status="posted", media_id=media_id, permalink=link,
                      posted_at=local_now().isoformat(timespec="minutes"))
            db.log(f"Posted trial reel “{reel['on_screen_text']}”")
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
                db.log(f"{h}h results for “{reel['on_screen_text']}”: {stats.get('views', 0):,} views")
                break  # one per reel per pass is plenty


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
            if _due_daily("radar", 5, 30, weekday=0) and env("APIFY_TOKEN", required=False) is not None:
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
    threading.Thread(target=_worker, daemon=True).start()
    threading.Thread(target=_clock, daemon=True).start()
