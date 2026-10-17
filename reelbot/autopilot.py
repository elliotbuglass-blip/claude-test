"""Autopilot: a queue of planned trial reels that post themselves at set times, plus result tracking.

Claude (the daily routine) writes a plan, e.g. data/plan.json:
[
  {"clip": "db12_night.mov", "on_screen_text": "All black spec… always",
   "post_caption": "All black spec… always 🖤", "angle": "spec flex",
   "seconds": 8, "start": null, "text_position": 0.16, "font_size": 60,
   "track": "dark_piano.mp3", "sound_suggestion": "Rondo in F Minor — Nicholas Britell",
   "post_at": "2026-10-18T09:00"}
]
`schedule plan.json` adds it to data/queue.json. `post-due` renders and posts whatever is due.
Videos are re-rendered at post time from the Drive clip, so nothing big has to be stored between runs.
"""

import copy
import json
import uuid
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import requests

from . import editor, session
from .settings import DATA, OUTPUT, ROOT, env

QUEUE = DATA / "queue.json"
LOG = DATA / "post_log.json"


def _load(path):
    return json.loads(path.read_text()) if path.exists() else []


def _save(path, data):
    DATA.mkdir(exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1))


def _tz(cfg):
    return ZoneInfo(cfg["posting"].get("timezone", "Europe/London"))


def schedule(cfg, plan_path):
    plan = json.loads((ROOT / plan_path).read_text())
    queue = _load(QUEUE)
    for item in plan:
        item.setdefault("id", uuid.uuid4().hex[:8])
        item["status"] = "scheduled"
        queue.append(item)
        print(f"  ⏰ {item['post_at']}  “{item['on_screen_text']}”  ({item['clip']})")
    _save(QUEUE, queue)
    print(f"{len(plan)} reel(s) scheduled.")


def next_slots(cfg, count):
    """The next `count` posting times from autopilot.post_times, starting tomorrow."""
    tz = _tz(cfg)
    day = datetime.now(tz).date() + timedelta(days=1)
    times = cfg["autopilot"]["post_times"]
    return [f"{day}T{times[i % len(times)]}" for i in range(count)]


def _clip_path(cfg, name):
    path = ROOT / cfg["clips"]["inbox_dir"] / name
    done = path.parent / "done" / name
    if path.exists():
        return path
    if done.exists():
        return done
    drive_id = json.loads(session.CLIPS.read_text()).get(name) if session.CLIPS.exists() else None
    if not drive_id:
        raise RuntimeError(f"Can't find clip {name} locally or in data/clips.json")
    return session.download(drive_id, path)


def render_item(cfg, item):
    """Render one planned reel with its own edit settings (hook, length, text spot, music)."""
    clip = _clip_path(cfg, item["clip"])
    look = {**cfg["look"], **{k: item[k] for k in ("text_position", "font_size", "text_style", "grade") if k in item}}
    audio = copy.deepcopy(cfg["audio"])
    if item.get("track"):
        audio.update(mode=item.get("audio_mode", "mix"), track=item["track"])
        session.sync_audio(cfg, session.list_folder(session.folder_id(cfg)))
    duration, has_audio = editor.probe(clip)
    length = min(item.get("seconds") or cfg["clips"]["reel_seconds"], duration)
    start = item.get("start")
    if start is None:
        start = editor.loudest_start(clip, duration, length) if has_audio else 0.0
    if look.get("text_position") in (None, "auto") or item.get("text_position") is None:
        style = editor.TEXT_STYLES[look.get("text_style", "editorial")]
        n_lines = len(editor.textwrap.wrap(editor.clean_text(item["on_screen_text"]), style["wrap"]))
        look["text_position"] = editor.auto_text_position(clip, start, length, n_lines, style["size"])
    out = OUTPUT / "review" / f"{item['id']}.mp4"
    out.parent.mkdir(parents=True, exist_ok=True)
    broll = None
    if item.get("broll"):
        b = item["broll"]
        broll = {**b, "clip": _clip_path(cfg, b["clip"])}
    editor.render(clip, out, editor.clean_text(item["on_screen_text"]), start, length, look, audio, broll)
    return out


def post_due(cfg, dry_run=False):
    from .publisher import post_reel

    now = datetime.now(_tz(cfg)).replace(tzinfo=None)
    queue = _load(QUEUE)
    due = [q for q in queue if q["status"] == "scheduled" and datetime.fromisoformat(q["post_at"]) <= now]
    if not due:
        print("Nothing due right now.")
        return
    log = _load(LOG)
    for item in due[: cfg["autopilot"].get("max_per_run", 2)]:
        try:
            video = render_item(cfg, item)
            caption = " ".join(x for x in (item.get("post_caption") or item["on_screen_text"],
                                           cfg["posting"].get("hashtags", "")) if x)
            if dry_run:
                print(f"  (dry run) rendered {video.name}: {caption!r}")
                continue
            item["media_id"] = post_reel(video, caption, cfg["posting"])
            item["status"] = "posted"
            item["posted_at"] = datetime.now(_tz(cfg)).isoformat(timespec="minutes")
            log.append({k: v for k, v in item.items() if k != "status"})
            print(f"  ✓ posted “{item['on_screen_text']}” (media {item['media_id']})")
        except Exception as e:  # keep the rest of the queue going
            item["status"] = "failed"
            item["error"] = str(e)[:300]
            print(f"  ✗ {item['id']}: {e}")
    _save(QUEUE, queue)
    _save(LOG, log)


METRICS = ["views", "reach", "likes", "comments", "saved", "shares",
           "ig_reels_avg_watch_time", "ig_reels_video_view_total_time"]


def results(cfg):
    """Fetch insights for every reel ReelBot posted, straight from Instagram (trial reels included)."""
    log = _load(LOG)
    token = env("IG_ACCESS_TOKEN", required=False)
    graph = f"https://graph.facebook.com/{cfg['posting']['graph_api_version']}"
    for item in log:
        if not item.get("media_id") or str(item["media_id"]).startswith("metricool"):
            continue
        stats = {}
        for metric in METRICS:  # one at a time: Meta rejects the whole call if any metric is unsupported
            params = {"metric": metric, **({"access_token": token} if token else {})}
            r = requests.get(f"{graph}/{item['media_id']}/insights", params=params, timeout=30)
            if r.ok and r.json().get("data"):
                stats[metric] = r.json()["data"][0]["values"][0]["value"]
        item["results"] = stats
        item["results_checked_at"] = datetime.now(_tz(cfg)).isoformat(timespec="minutes")
    _save(LOG, log)
    rows = sorted((i for i in log if i.get("results")), key=lambda i: i["results"].get("views", 0), reverse=True)
    for i in rows:
        r = i["results"]
        print(f"  {r.get('views', 0):>8,} views  {r.get('shares', 0):>4} shares  "
              f"[{i.get('angle', '')}] “{i['on_screen_text']}”  ♪ {i.get('track') or 'original'}")
    return log


BEST_TIMES = DATA / "best_times.json"


def best_times(cfg, max_reels=150):
    """Work out which posting hours get the most views, from my own reel history (UK time).

    Uses the median (not average) views per hour, so one viral reel doesn't skew it,
    and needs at least 3 reels in an hour before trusting it.
    """
    import statistics
    from collections import defaultdict

    token = env("IG_ACCESS_TOKEN", required=False)
    auth = {"access_token": token} if token else {}
    graph = f"https://graph.facebook.com/{cfg['posting']['graph_api_version']}"
    url, params, reels = f"{graph}/{env('IG_USER_ID')}/media", {"fields": "id,timestamp,media_product_type", "limit": 50, **auth}, []
    while url and len(reels) < max_reels:
        r = requests.get(url, params=params, timeout=60).json()
        reels += [m for m in r.get("data", []) if m.get("media_product_type") == "REELS"]
        url, params = r.get("paging", {}).get("next"), {}

    tz = _tz(cfg)
    by_hour = defaultdict(list)
    for m in reels[:max_reels]:
        r = requests.get(f"{graph}/{m['id']}/insights", params={"metric": "views", **auth}, timeout=30)
        if not (r.ok and r.json().get("data")):
            continue
        views = r.json()["data"][0]["values"][0]["value"]
        hour = datetime.fromisoformat(m["timestamp"].replace("+0000", "+00:00")).astimezone(tz).hour
        by_hour[hour].append(views)

    table = sorted(({"hour": h, "reels": len(v), "median_views": int(statistics.median(v))}
                    for h, v in by_hour.items() if len(v) >= 3),
                   key=lambda x: x["median_views"], reverse=True)
    result = {"checked_at": datetime.now(tz).isoformat(timespec="minutes"), "reels_used": sum(len(v) for v in by_hour.values()),
              "hours": table, "recommended": [f"{t['hour']:02d}:00" for t in table[: cfg["autopilot"]["posts_per_day"]]]}
    _save(BEST_TIMES, result)
    for t in table:
        print(f"  {t['hour']:02d}:00  median {t['median_views']:>9,} views  ({t['reels']} reels)")
    print("Recommended posting times:", ", ".join(sorted(result["recommended"])))
    return result
