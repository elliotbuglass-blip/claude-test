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
    "posts_per_day": ("autopilot.posts_per_day", "Posts per day"),
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


def add_clip(path, filename, kind=None):
    clip_id = db.new_id()
    duration, _ = editor.probe(path)
    db.insert("clips", {"id": clip_id, "filename": filename, "path": str(path), "duration": duration,
                        "kind": kind or "main", "notes": "kind set by you" if kind else "",
                        "broll_silent": 1 if setting("broll_silent") else 0})
    submit(f"analyse {filename}", analyse_clip, clip_id, kind is None)
    return clip_id


def analyse_clip(clip_id, decide_kind=True):
    clip = db.one("SELECT * FROM clips WHERE id = ?", clip_id)
    db.update("clips", clip_id, status="analysing")
    duration, has_audio = editor.probe(clip["path"])
    loud = editor.loudest_start(clip["path"], duration, min(8, duration)) + 1.0 if has_audio else 0.0
    info = brain.analyse_clip(_frames(clip["path"], 4), duration, has_audio, loud, cfg()["niche"])
    fields = {"subject": info["subject"], "hashtags": json.dumps(info["hashtags"]), "status": "analysed",
              "notes": f"{info['mood']} · {info['highlight']}"}
    if decide_kind:
        fields["kind"] = info["kind"]
        fields["notes"] += f" · {info['kind']}: {info['kind_reason']}"
    db.update("clips", clip_id, **fields)
    db.log(f"Analysed {clip['filename']}: {info['subject']} ({fields.get('kind', clip['kind'])})")
    if fields.get("kind", clip["kind"]) == "main" and setting("mode") == "review":
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
        reels += [m for m in r.get("data", []) if m.get("media_product_type") == "REELS"]
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

def posting_times():
    if setting("times_mode") == "manual":
        return sorted(setting("post_times") or ["09:00", "12:00", "15:00", "18:00", "21:00"])
    best = db.latest_research("best_times")
    return best["recommended"] if best and best["recommended"] else ["07:00", "11:00", "13:00", "15:00", "16:00"]


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
    rows = db.q("""SELECT r.angle, r.sound_suggestion, r.track, r.virality_score, r.on_screen_text,
                          MAX(s.hours) AS hours, s.views FROM reels r JOIN snapshots s ON s.reel_id = r.id
                   GROUP BY r.id""")
    if not rows:
        return "No ReelBot trial reels with results yet."
    by_angle = defaultdict(list)
    for r in rows:
        by_angle[r["angle"]].append(r["views"] or 0)
    lines = [f"- angle '{a}': {len(v)} reels, median {int(statistics.median(v)):,} views"
             for a, v in sorted(by_angle.items(), key=lambda x: -statistics.median(x[1]))]
    best = sorted(rows, key=lambda r: -(r["views"] or 0))[:5]
    worst = sorted(rows, key=lambda r: r["views"] or 0)[:5]
    lines.append("Best: " + " | ".join(f'"{r["on_screen_text"]}" {r["views"]:,} (predicted {r["virality_score"]})' for r in best))
    lines.append("Worst: " + " | ".join(f'"{r["on_screen_text"]}" {r["views"]:,} (predicted {r["virality_score"]})' for r in worst))
    return "\n".join(lines)


def build_context(topic):
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
    trends = db.latest_research("trends")
    if trends and trends.get("items"):
        parts.append("TRENDING NOW on Google (search term · searches · headline):\n" + "\n".join(
            f'- {t["term"]} · {t["searches"]} · {t["headline"][:90]}' for t in trends["items"][:30]))
    radar = db.latest_research("radar")
    if radar and radar.get("outliers"):
        parts.append("COMPETITOR OUTLIERS (beat their own median):\n" + "\n".join(
            f'- @{o["account"]}: "{o.get("on_screen_text") or o.get("post_caption", "")[:60]}" {o["ratio"]}x, {o["views"]:,} views'
            for o in radar["outliers"][:12]))
    used = [r["on_screen_text"] for r in db.q("SELECT on_screen_text FROM reels WHERE status != 'rejected'")]
    if used:
        parts.append("HOOKS ALREADY USED (don't repeat):\n" + "\n".join(used[-60:]))
    return "\n\n".join(parts)


def make_reels(clip_id, n=None, post_at=None):
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
    library = sorted(p.name for p in db.AUDIO_DIR.glob("*") if p.suffix.lower() in editor.AUDIO_EXTS)
    info = {"filename": clip["filename"], "subject": clip["subject"], "notes": clip["notes"], "seconds": clip["duration"]}
    plans = brain.plan_reels(_frames(clip["path"], 3), info, n, build_context(topic), library)
    mode = setting("mode")
    slots = post_at or next_free_slots(len(plans))
    research = research_snapshot(topic)
    for plan, slot in zip(plans, slots):
        reel_id = db.new_id()
        trend = plan.get("trend") or ""
        db.insert("reels", {
            "id": reel_id, "clip_id": clip_id,
            **{k: plan[k] for k in plan if k not in ("track", "positives", "negatives", "trend")},
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


def research_snapshot(topic):
    """The research a batch of reels was planned from, kept with each reel for its "Why this reel" panel."""
    out = {"winners": [], "sounds": [], "sounds_7d": [], "original_share": None, "outliers": [], "hashtags": []}
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
                          "sound moment (engine/rev), so the payoff lands inside the reel" if has_audio
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
    """Autopilot: tomorrow's posts from clips that haven't been used yet (oldest first)."""
    if setting("mode") != "autopilot":
        return
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
    per_clip = math.ceil(len(slots) / len(clips))
    for clip in clips:
        mine = slots[:per_clip]
        slots = slots[per_clip:]
        if mine:
            make_reels(clip["id"], len(mine), post_at=mine)
    db.log(f"Autopilot planned {n} trial reels for {tomorrow}")


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
            if _due_daily("radar", 5, 30, weekday=0) and env("APIFY_TOKEN", required=False) is not None:
                submit("competitor radar", run_radar)
        except Exception as e:
            db.log(f"✗ clock: {e}")
        tick += 1
        time.sleep(60)


def start():
    threading.Thread(target=_worker, daemon=True).start()
    threading.Thread(target=_clock, daemon=True).start()
