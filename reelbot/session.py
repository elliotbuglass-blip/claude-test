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


def pull(cfg):
    """Download clips from the Drive folder that haven't been used before."""
    seen = set(json.loads(SEEN.read_text())) if SEEN.exists() else set()
    files = _drive_get(DRIVE, q=f"'{folder_id(cfg)}' in parents and trashed = false",
                       fields="files(id,name,mimeType,size)", pageSize=1000).json().get("files", [])
    inbox = ROOT / cfg["clips"]["inbox_dir"]
    inbox.mkdir(exist_ok=True)
    new = []
    for f in files:
        if f["id"] in seen or not f["name"].lower().endswith(VIDEO_EXTS + (".txt",)):
            continue
        with _drive_get(f"{DRIVE}/{f['id']}", alt="media") as r, (inbox / f["name"]).open("wb") as out:
            for chunk in r.iter_content(1 << 20):
                out.write(chunk)
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
