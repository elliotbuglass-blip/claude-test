"""Cuts a clip into a vertical reel, gives it a moody look, adds on-screen text and audio."""

import array
import json
import random
import re
import subprocess
import textwrap
from pathlib import Path

VIDEO_EXTS = {".mp4", ".mov", ".m4v", ".mkv"}
AUDIO_EXTS = {".mp3", ".m4a", ".wav", ".aac"}
W, H = 1080, 1920


def _run(cmd):
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed:\n{result.stderr[-2000:]}")
    return result.stdout


def probe(path):
    out = _run(["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)])
    info = json.loads(out)
    has_audio = any(s["codec_type"] == "audio" for s in info["streams"])
    return float(info["format"]["duration"]), has_audio


def loudest_start(path, duration, length, window=0.25):
    """Find where the clip is loudest (engine rev, cold start) and start the reel just before it."""
    rate = 8000
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path), "-ac", "1", "-ar", str(rate), "-f", "s16le", "-"],
        capture_output=True,
    ).stdout
    samples = array.array("h", raw)
    step = int(rate * window)
    energy = [
        sum(s * s for s in samples[i:i + step]) / step
        for i in range(0, max(len(samples) - step, 0), step)
    ]
    per_reel = max(int(length / window), 1)
    if len(energy) <= per_reel:
        return 0.0
    # Slide a reel-length window over the clip and keep the loudest stretch.
    cur = sum(energy[:per_reel])
    best_i, best_sum = 0, cur
    for i in range(1, len(energy) - per_reel + 1):
        cur += energy[i + per_reel - 1] - energy[i - 1]
        if cur > best_sum:
            best_i, best_sum = i, cur
    # Find where the noise kicks in inside that stretch, and start one second before it
    # so the hook text has a beat before the rev hits.
    chunk = energy[best_i:best_i + per_reel]
    onset = best_i + next(i for i, e in enumerate(chunk) if e >= max(chunk) * 0.5)
    return max(min(onset * window - 1.0, duration - length), 0.0)


def extract_frame(path, at_seconds, out_path):
    _run(["ffmpeg", "-y", "-v", "error", "-ss", f"{at_seconds:.2f}", "-i", str(path),
          "-frames:v", "1", "-vf", "scale=540:-2", str(out_path)])
    return out_path


# drawtext can't render emoji (they come out as empty boxes), so strip them from burned-in text.
EMOJI = re.compile("[\U0001F000-\U0001FAFF\u2600-\u27BF\uFE0F\u200D]+")


def clean_text(text):
    return " ".join(EMOJI.sub("", text).split())


def _escape(text):
    return text.replace("\\", "\\\\").replace("'", "’").replace(":", "\\:").replace("%", "\\%")


FONT_FALLBACKS = [
    "/System/Library/Fonts/Helvetica.ttc",                    # Mac
    "/System/Library/Fonts/Supplemental/Arial.ttf",           # Mac
    "C\\:/Windows/Fonts/arial.ttf",                          # Windows
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",        # Linux
]


def _font(path):
    for candidate in [path, *FONT_FALLBACKS]:
        if candidate and Path(candidate.replace("\\", "")).exists():
            return candidate
    raise SystemExit(f"Font not found: {path}. Set look.font in config.yaml to a .ttf/.otf on your computer.")


FONT_DIR = Path(__file__).parent / "fonts"

# Text looks. "editorial" matches @elliotcameron._'s reels: small, thin serif, plain white.
TEXT_STYLES = {
    "editorial": {"font": str(FONT_DIR / "LiberationSerif-Regular.ttf"), "size": 46, "wrap": 34, "shadow": 0.25},
    "stacked":   {"font": str(FONT_DIR / "LiberationSerif-Regular.ttf"), "size": 96, "wrap": 8, "shadow": 0.25},
    "classic":   {"font": "/usr/share/fonts/opentype/inter/Inter-SemiBold.otf", "size": 60, "wrap": 22, "shadow": 0.55},
}

# Colour looks. "natural" keeps real colour (blue calipers, deep blacks), slightly low exposure.
GRADES = {
    "natural": "eq=contrast=1.08:brightness=-0.045:saturation=1.1:gamma=0.95",
    "moody": "eq=contrast=1.08:brightness=-0.03:saturation=0.82,vignette=PI/5",
    "none": None,
}


def _text_filters(caption, look):
    style = TEXT_STYLES[look.get("text_style", "editorial")]
    size = look.get("font_size") or style["size"]
    font = _font(look.get("font") or style["font"])
    lines = textwrap.wrap(clean_text(caption), width=style["wrap"]) or [""]
    line_h = int(size * 1.18)
    top = int(H * look["text_position"])
    shadow = f":shadowcolor=black@{style['shadow']}:shadowx=1:shadowy=2" if style["shadow"] else ""
    return [
        f"drawtext=fontfile='{font}':text='{_escape(line)}':fontsize={size}:fontcolor=white{shadow}"
        f":x=(w-text_w)/2:y={top + i * line_h}"
        for i, line in enumerate(lines)
    ]


def pick_track(folder):
    tracks = [p for p in Path(folder).glob("*") if p.suffix.lower() in AUDIO_EXTS]
    return random.choice(tracks) if tracks else None


def render(clip, out_path, caption, start, length, look, audio_cfg, broll=None):
    """Make one reel. broll = {"clip": path, "start": s, "at": s, "seconds": s} cuts a b-roll
    shot in over the main clip (the main clip's sound keeps playing underneath)."""
    frame = f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps=30"
    grade = GRADES[look.get("grade") or ("moody" if look.get("moody_grade") else "natural")]

    _, has_audio = probe(clip)
    mode = audio_cfg["mode"]
    track = None
    if mode in ("music", "mix"):
        chosen = audio_cfg.get("track")
        track = Path(audio_cfg["folder"]) / chosen if chosen else pick_track(audio_cfg["folder"])
        if track is None or not track.exists():
            print(f"  (no music track found in {audio_cfg['folder']}/, keeping original sound)")
            track, mode = None, "original"

    cmd = ["ffmpeg", "-y", "-v", "error", "-ss", f"{start:.2f}", "-t", f"{length:.2f}", "-i", str(clip)]
    video = f"[0:v]{frame},setpts=PTS-STARTPTS[base]"
    last = "base"
    n = 1
    if broll:
        at, dur = float(broll["at"]), float(broll["seconds"])
        cmd += ["-ss", f"{float(broll.get('start', 0)):.2f}", "-t", f"{dur:.2f}", "-i", str(broll["clip"])]
        video += (f";[{n}:v]{frame},setpts=PTS-STARTPTS+{at}/TB[br]"
                  f";[base][br]overlay=enable='between(t,{at},{at + dur})':eof_action=pass[ov]")
        last, n = "ov", n + 1
    post = [f for f in [grade, *_text_filters(caption, look)] if f]
    video += f";[{last}]{','.join(post)}[v]"

    fade = f"afade=t=out:st={max(length - 0.6, 0):.2f}:d=0.6"
    if mode == "original":
        audio = f";[0:a]{fade}[a]" if has_audio else ""
    else:
        # Loop the track if it's shorter than the reel, and level it so every track sits at the same loudness.
        cmd += ["-stream_loop", "-1", "-i", str(track)]
        music = f"[{n}:a]loudnorm=I=-14:TP=-1.5:LRA=11,volume={audio_cfg['music_volume']}"
        if mode == "mix" and has_audio:
            audio = (f";{music}[m];[0:a]volume={audio_cfg['original_volume']}[o];"
                     f"[m][o]amix=inputs=2:duration=first:normalize=0,{fade}[a]")
        else:
            audio = f";{music},{fade}[a]"
    cmd += ["-filter_complex", video + audio, "-map", "[v]"]
    cmd += ["-map", "[a]"] if audio else ["-an"]

    tmp = out_path.with_suffix(".tmp.mp4")
    cmd += ["-t", f"{length:.2f}", "-c:v", "libx264", "-preset", "medium", "-crf", "20",
            "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-ar", "44100",
            "-movflags", "+faststart", str(tmp)]
    _run(cmd)
    # Re-mux to drop the H.264 edit list, which makes some players show a black first frame.
    _run(["ffmpeg", "-y", "-v", "error", "-fflags", "+genpts+igndts", "-i", str(tmp),
          "-c", "copy", "-movflags", "+faststart", str(out_path)])
    tmp.unlink(missing_ok=True)
    return track
