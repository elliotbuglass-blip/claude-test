"""Reads the text burned INTO a reel (not the post caption) by showing Claude a few frames.

Results are cached in data/onscreen_text.json so each reel is only read once.
"""

import base64
import json
import subprocess
import tempfile

import anthropic
import requests

from .settings import claude, DATA

MODEL = "claude-opus-5-5"
CACHE = DATA / "onscreen_text.json"
FRAME_TIMES = (0.5, 2.0, 4.5)  # hook text usually appears in the first few seconds

SCHEMA = {
    "type": "object",
    "properties": {
        "on_screen_text": {"type": "string"},
        "visual": {"type": "string"},
    },
    "required": ["on_screen_text", "visual"],
    "additionalProperties": False,
}

PROMPT = """These are frames from one Instagram reel, in time order.

on_screen_text: write out, word for word, the text that was edited onto the video (the hook/caption overlay). Keep the creator's spelling, punctuation and emoji. If the text changes between frames, join the pieces with " / " in order. Ignore Instagram's own interface, watermarks, usernames, number plates and signs that are just part of the scene. If there is no overlay text, return an empty string.

visual: one short line describing what the video shows (subject, setting, mood), e.g. "black Aston Martin DB12 cold start in an underground car park at night"."""


def _cache():
    return json.loads(CACHE.read_text()) if CACHE.exists() else {}


def _frame_from_video(url_or_path, t):
    result = subprocess.run(
        ["ffmpeg", "-v", "error", "-ss", str(t), "-i", str(url_or_path), "-frames:v", "1",
         "-vf", "scale=540:-2", "-f", "image2pipe", "-vcodec", "mjpeg", "-"],
        capture_output=True, timeout=120,
    )
    return result.stdout or None


def _download(url):
    try:
        resp = requests.get(url, timeout=60)
        return resp.content if resp.ok else None
    except requests.RequestException:
        return None


def gather_frames(video=None, thumbnail=None):
    frames = []
    if video and str(video).startswith("http"):
        # Download with requests first: it goes through the network proxy, ffmpeg doesn't.
        data = _download(video)
        if data:
            with tempfile.NamedTemporaryFile(suffix=".mp4") as tmp:
                tmp.write(data)
                tmp.flush()
                frames = [f for f in (_frame_from_video(tmp.name, t) for t in FRAME_TIMES) if f]
    elif video:
        frames = [f for f in (_frame_from_video(video, t) for t in FRAME_TIMES) if f]
    if not frames and thumbnail:
        # No video available (e.g. reels with licensed music) — the cover frame
        # usually still shows the hook text.
        img = _download(thumbnail)
        if img:
            frames = [img]
    return frames


def ask_claude(frames):
    client = claude()
    content = [
        {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg",
                                     "data": base64.standard_b64encode(f).decode()}}
        for f in frames
    ]
    content.append({"type": "text", "text": PROMPT})
    response = client.beta.messages.create(
        model=MODEL,
        max_tokens=2000,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        output_config={"effort": "low", "format": {"type": "json_schema", "schema": SCHEMA}},
        messages=[{"role": "user", "content": content}],
    )
    if response.stop_reason == "refusal":
        return {"on_screen_text": "", "visual": ""}
    return json.loads(next(b.text for b in response.content if b.type == "text"))


def read_reels(items):
    """items: list of dicts with "key" and optionally "video"/"thumbnail".

    Returns {key: {"on_screen_text", "visual"}} for every item that could be read.
    """
    cache = _cache()
    todo = [it for it in items if it["key"] not in cache]
    for n, it in enumerate(todo, 1):
        frames = gather_frames(it.get("video"), it.get("thumbnail"))
        if not frames:
            print(f"  ! no frames for {it['key']} (video and thumbnail unavailable)")
            continue
        cache[it["key"]] = ask_claude(frames)
        print(f"  [{n}/{len(todo)}] {it['key']}: “{cache[it['key']]['on_screen_text']}”")
        DATA.mkdir(exist_ok=True)
        CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=1))  # save as we go
    return {it["key"]: cache[it["key"]] for it in items if it["key"] in cache}


def remember(key, on_screen_text, visual=""):
    """Record text we burned in ourselves, so we never pay to read our own reels."""
    cache = _cache()
    cache[key] = {"on_screen_text": on_screen_text, "visual": visual}
    DATA.mkdir(exist_ok=True)
    CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=1))
