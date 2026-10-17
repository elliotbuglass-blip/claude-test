"""Helpers for running ReelBot inside a Claude Code chat, where Claude itself is the "brain".

- pull:  download new clips from your shared Google Drive folder into inbox/
- radar: find competitor outlier reels and save frames for Claude to read (no Anthropic API needed)
"""

import json
import re

import requests

from . import competitors, vision
from .settings import DATA, OUTPUT, ROOT, env

DRIVE = "https://www.googleapis.com/drive/v3/files"
SEEN = DATA / "seen_clips.json"
CLIPS = DATA / "clips.json"  # clip file name → Drive id, so later runs can re-download it
VIDEO_EXTS = (".mp4", ".mov", ".m4v")


def _drive_get(url, **params):
    # API key is an env var, or added by a Claude Code network secret
    # (header X-Goog-Api-Key on www.googleapis.com) — then it's blank here.
    key = env("GOOGLE_API_KEY", required=False)
    if key:
        params["key"] = key
    resp = requests.get(url, params=params, timeout=600, stream=params.get("alt") == "media")
    if not resp.ok:
        raise SystemExit(f"Google Drive error ({resp.status_code}): {resp.text[:300]}\n"
                         "Check the folder is shared as 'Anyone with the link' and the Google secret is set.")
    return resp


def folder_id(cfg):
    m = re.search(r"folders/([\w-]+)", cfg.get("drive_folder", ""))
    return m.group(1) if m else cfg.get("drive_folder", "")


def list_folder(fid):
    return _drive_get(DRIVE, q=f"'{fid}' in parents and trashed = false",
                      fields="files(id,name,mimeType,size)", pageSize=1000).json().get("files", [])


def download(file_id, dest):
    dest.parent.mkdir(parents=True, exist_ok=True)
    with _drive_get(f"{DRIVE}/{file_id}", alt="media") as r, dest.open("wb") as out:
        for chunk in r.iter_content(1 << 20):
            out.write(chunk)
    return dest


def sync_audio(cfg, files):
    """Download music tracks from an 'audio' subfolder of the Drive folder (for autopilot)."""
    sub = next((f for f in files if f["mimeType"].endswith("folder") and f["name"].lower() == "audio"), None)
    if not sub:
        return []
    folder = ROOT / cfg["audio"]["folder"]
    got = []
    for f in list_folder(sub["id"]):
        if f["name"].lower().endswith((".mp3", ".m4a", ".wav", ".aac")) and not (folder / f["name"]).exists():
            download(f["id"], folder / f["name"])
            got.append(f["name"])
    if got:
        print(f"  ♪ {len(got)} new track(s) from Drive audio/")
    return got


def pull(cfg):
    """Download clips from the Drive folder that haven't been used before."""
    seen = set(json.loads(SEEN.read_text())) if SEEN.exists() else set()
    files = list_folder(folder_id(cfg))
    sync_audio(cfg, files)
    clips = json.loads(CLIPS.read_text()) if CLIPS.exists() else {}
    clips.update({f["name"]: f["id"] for f in files if f["name"].lower().endswith(VIDEO_EXTS)})
    DATA.mkdir(exist_ok=True)
    CLIPS.write_text(json.dumps(clips, indent=1))
    inbox = ROOT / cfg["clips"]["inbox_dir"]
    inbox.mkdir(exist_ok=True)
    new = []
    for f in files:
        if f["id"] in seen or not f["name"].lower().endswith(VIDEO_EXTS + (".txt",)):
            continue
        download(f["id"], inbox / f["name"])
        seen.add(f["id"])
        new.append(f["name"])
        print(f"  ↓ {f['name']}")
    DATA.mkdir(exist_ok=True)
    SEEN.write_text(json.dumps(sorted(seen), indent=1))
    print(f"{len(new)} new file(s) from Drive ({len(files)} in the folder).")
    return new


def radar(cfg):
    """Find outliers and save 3 frames of each to output/radar/ for Claude to look at."""
    competitors.vision.read_reels = lambda items: {}  # Claude reads the frames itself in this mode
    radar_cfg = cfg["radar"]
    outliers = []
    accounts = []
    for c in cfg["competitors"]:
        name = c["username"] if isinstance(c, dict) else c
        fetch = {"meta": competitors.fetch_account_meta, "hiker": competitors.fetch_account}.get(
            radar_cfg.get("source"), competitors.fetch_account_apify)
        acc = fetch(name, radar_cfg["reels_per_account"])
        if acc:
            print(f"  ✓ @{name}: {len(acc['reels'])} reels")
            accounts.append(acc)
    competitors._print_distribution(accounts)
    outliers = competitors.find_outliers(accounts, radar_cfg)
    frames_dir = OUTPUT / "radar"
    frames_dir.mkdir(parents=True, exist_ok=True)
    for o in outliers:
        frames = vision.gather_frames(o.get("video"), o.get("thumbnail"))
        o["frames"] = []
        for i, img in enumerate(frames, 1):
            path = frames_dir / f"{o['account']}_{o['code']}_{i}.jpg"
            path.write_bytes(img)
            o["frames"].append(str(path.relative_to(ROOT)))
        o.pop("video", None)
        o.pop("thumbnail", None)
    DATA.mkdir(exist_ok=True)
    competitors.OUTLIERS.write_text(json.dumps(outliers, ensure_ascii=False, indent=1))
    print(f"\n{len(outliers)} outliers saved to data/competitors.json, frames in output/radar/")
    for o in outliers[:15]:
        print(f"  {o['ratio']:>5}x {o['views']:>10,}  @{o['account']}  {o['url']}")
    return outliers


APIFY_HASHTAG = "https://api.apify.com/v2/acts/apify~instagram-hashtag-scraper/run-sync-get-dataset-items"


def topic(cfg, hashtags, per_tag=40, keywords=()):
    """Research a topic (e.g. Aston Martin) two ways and save frames for Claude to read:

    1. Instagram-wide: top recent reels for each hashtag (via Apify).
    2. My competitors: their outlier reels whose caption mentions the topic.
    Also tallies which sounds the top reels used.
    """
    from collections import Counter

    token = env("APIFY_TOKEN", required=False)
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    tags = [h.lstrip("#").lower() for h in hashtags]
    resp = requests.post(APIFY_HASHTAG, json={"hashtags": tags, "resultsType": "reels",
                                              "resultsLimit": per_tag},
                         headers=headers, timeout=900)
    resp.raise_for_status()
    now = __import__("time").time()
    reels = [r for r in (competitors.apify_reel(i) for i in resp.json()) if r]
    reels = [r for r in reels if now - r["taken_at"] <= 60 * 86400]  # last 2 months only
    reels.sort(key=lambda r: r["views"], reverse=True)
    top = reels[:15]

    # Competitor outliers about the same topic (from the last radar run)
    words = [w.lower() for w in (*tags, *keywords)]
    comp = [o for o in competitors.load()
            if any(w in (o.get("post_caption") or "").lower().replace(" ", "") for w in words)]

    frames_dir = OUTPUT / "topic"
    frames_dir.mkdir(parents=True, exist_ok=True)
    for r in top:
        r["frames"] = []
        for i, img in enumerate(vision.gather_frames(r.get("video"), r.get("thumbnail")), 1):
            path = frames_dir / f"{r['code']}_{i}.jpg"
            path.write_bytes(img)
            r["frames"].append(str(path.relative_to(ROOT)))
        r.pop("video", None)
        r.pop("thumbnail", None)

    sounds = Counter(r["music"] for r in reels[:30] if r.get("music") and r["music"] != "original audio")
    result = {"hashtags": tags, "top_reels": top, "competitor_matches": comp,
              "trending_sounds": sounds.most_common(10)}
    DATA.mkdir(exist_ok=True)
    (DATA / "topic_research.json").write_text(json.dumps(result, ensure_ascii=False, indent=1))

    print(f"{len(reels)} recent reels found for #{' #'.join(tags)}. Top 15 (frames in output/topic/):")
    for r in top:
        print(f"  {r['views']:>10,}  @{r['account']}  🎵 {r.get('music') or '?'}  {r['url']}")
    print(f"\n{len(comp)} competitor outliers about this topic.")
    print("Most-used sounds:", ", ".join(f"{s} ({n})" for s, n in sounds.most_common(5)) or "none")
    return result
