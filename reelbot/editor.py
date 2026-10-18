"""Cuts a clip into a vertical reel, gives it a moody look, adds on-screen text and audio."""

import array
import json
import os
import random
import re
import subprocess
import textwrap
from pathlib import Path

VIDEO_EXTS = {".mp4", ".mov", ".m4v", ".mkv"}
AUDIO_EXTS = {".mp3", ".m4a", ".wav", ".aac"}
W, H = 1080, 1920


# Small servers have little memory: decode 4K with a couple of threads, not one per CPU core.
THREADS = os.environ.get("REELBOT_FFMPEG_THREADS", "4")


def _run(cmd):
    if cmd[0] == "ffmpeg" and "-threads" not in cmd:
        cmd = [x for part in cmd for x in (["-threads", THREADS, part] if part == "-i" else [part])]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        if result.returncode < 0 or not result.stderr.strip():
            raise RuntimeError(f"{cmd[0]} was stopped by the server (code {result.returncode}): usually it ran out of memory")
        raise RuntimeError(f"{cmd[0]} failed:\n{result.stderr[-2000:]}")
    return result.stdout


HDR_TRANSFERS = {"arib-std-b67": "arib-std-b67", "smpte2084": "smpte2084"}  # iPhone HLG / Dolby Vision, HDR10
SDR_TAGS = ["-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709"]


def _video_info(path):
    return json.loads(_run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                            "stream=width,height,color_transfer", "-of", "json", str(path)]))["streams"][0]


def to_sdr(transfer):
    """Filter that turns iPhone HDR into normal (SDR) video. Without it the colours come out flat and washed out."""
    return (f"zscale=tin={transfer}:min=bt2020nc:pin=bt2020:rin=tv:t=linear:npl=203,format=gbrpf32le,"
            "zscale=p=bt709,tonemap=mobius:desat=0,zscale=t=bt709:m=bt709:r=tv,format=yuv420p")


def working_copy(path):
    """Shrink a 4K phone clip to a 1080p SDR working copy (the reel is 1080x1920 anyway).
    Uses far less memory, disk and time for every later step, and converts iPhone HDR to normal colour.
    Returns the new path, or the old one if it's small and SDR already."""
    path = Path(path)
    info = _video_info(path)
    hdr = HDR_TRANSFERS.get(info.get("color_transfer", ""))
    if min(info["width"], info["height"]) <= 1080 and not hdr:
        return path
    out = path.with_name(f"{path.stem.removesuffix('_1080')}_1080{'_sdr' if hdr else ''}.mp4")
    vf = "scale='if(gt(iw,ih),-2,1080)':'if(gt(iw,ih),1080,-2)'" + (f",{to_sdr(hdr)}" if hdr else "")
    _run(["ffmpeg", "-y", "-v", "error", "-threads", THREADS, "-i", str(path),  # 4K decoding is the memory hog
          "-vf", vf, *SDR_TAGS,
          "-c:v", "libx264", "-preset", "veryfast", "-crf", "17", "-x264-params", "rc-lookahead=10", "-threads", THREADS,
          "-pix_fmt", "yuv420p",
          "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(out)])
    return out


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


# Instagram covers the top (header) and the bottom of a reel (profile, caption, buttons: ~35% when the caption is
# long, ~25% for a one-line caption). 0.68 leaves room for the dark console in car interiors, the best spot there.
SAFE_TOP, SAFE_BOTTOM = 0.14, 0.68


def _gray_frames(clip, start, length, w, h, n=5):
    frames = []
    for i in range(n):
        t = start + length * (i + 0.5) / n
        raw = subprocess.run(
            ["ffmpeg", "-v", "error", "-ss", f"{t:.2f}", "-i", str(clip), "-frames:v", "1",
             "-vf", f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},scale={w}:{h},format=gray",
             "-f", "rawvideo", "-"], capture_output=True).stdout
        if len(raw) == w * h:
            frames.append(raw)
    return frames


def text_spots(clip, start, length, n_lines=1, size=40, k=4, spread=False, ends=False):
    """Up to k candidate text positions inside Instagram's safe zone, best first
    (or, with spread=True, spaced out from top to bottom of the safe zone;
    or, with ends=True, k//2 near the top and k//2 near the bottom: centred text never sits mid-frame).

    A good spot is dark enough for white text and *calm*: few edges, so it's empty
    background (wall, sky, floor, seat) rather than the car, the wheel, hands or a face.
    """
    w, h = 108, 192
    frames = _gray_frames(clip, start, length, w, h)
    if not frames:
        return [(0.3, 0.0)]
    block = max(int(h * (n_lines * size * 1.18 / H)) + 2, 3)
    x0, x1 = int(w * 0.12), int(w * 0.88)
    scored = []
    for top in range(int(h * SAFE_TOP), int(h * SAFE_BOTTOM) - block + 1):
        bright = edges = count = 0
        for f in frames:
            for y in range(top, top + block):
                row = y * w
                for x in range(x0, x1):
                    v = f[row + x]
                    bright += v
                    edges += abs(v - f[row + x + 1]) + abs(v - f[row + w + x])
                    count += 1
        scored.append((top / h, 0.5 * bright / count + 3.0 * edges / count))
    def even(bands, n, picks):  # n evenly spaced bands, each nudged to its calmest nearby spot
        step = (bands[-1][0] - bands[0][0]) / max(n - 1, 1)
        for i in range(n):
            target = bands[0][0] + i * step
            near = [x for x in bands if abs(x[0] - target) <= step / 2 + 1e-9
                    and all(abs(x[0] - p) > block / h for p, _ in picks)]
            if near:
                pos, score = min(near, key=lambda x: x[1])
                picks.append((round(pos, 3), round(score, 1)))
        return picks

    if ends:  # the top and bottom of the safe zone (about a sixth of the frame each)
        span = 0.17
        top_bands = [x for x in scored if x[0] <= scored[0][0] + span]
        bottom_bands = [x for x in scored if x[0] >= scored[-1][0] - span]
        return even(bottom_bands, k - k // 2, even(top_bands, k // 2, []))
    if spread:  # evenly spaced bands top to bottom
        return even(scored, k, [])
    scored.sort(key=lambda s: s[1])
    picks = []
    for pos, score in scored:  # keep spots that don't overlap each other
        if all(abs(pos - p) > block / h for p, _ in picks):
            picks.append((round(pos, 3), round(score, 1)))
        if len(picks) == k:
            break
    return picks


def band_brightness(clip, start, length, pos, n_lines=1, size=40):
    """Average brightness (0–255) of the strip the text will sit on."""
    w, h = 108, 192
    frames = _gray_frames(clip, start, length, w, h, n=3)
    top = int(pos * h)
    block = max(int(h * (n_lines * size * 1.18 / H)) + 2, 3)
    vals = [f[y * w + x] for f in frames for y in range(top, min(top + block, h)) for x in range(int(w * 0.2), int(w * 0.8))]
    return sum(vals) / len(vals) if vals else 0


def auto_text_position(clip, start, length, n_lines=1, size=40):
    """The best text spot by the calm/dark measure alone (used when Claude isn't available)."""
    return text_spots(clip, start, length, n_lines, size, k=1)[0][0]


def spots_preview(clip, start, length, spots, n_lines, size, out_path):
    """A picture of 3 moments from the reel with the candidate text spots drawn as numbered boxes."""
    block = n_lines * size * 1.18
    boxes = ",".join(
        f"drawbox=x=iw*0.12:y={int(pos * H)}:w=iw*0.76:h={int(block)}:color=yellow@0.9:t=6,"
        f"drawtext=fontfile='{FONT_DIR / 'LiberationSerif-Regular.ttf'}':text='{i + 1}':fontsize=90:fontcolor=yellow"
        f":x=w*0.04:y={int(pos * H)}"
        for i, (pos, _) in enumerate(spots))
    parts = []
    for i in range(3):
        t = start + length * (i + 0.5) / 3
        part = out_path.with_name(f"{out_path.stem}_{i}.jpg")
        _run(["ffmpeg", "-y", "-v", "error", "-ss", f"{t:.2f}", "-i", str(clip), "-frames:v", "1", "-vf",
              f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},{boxes},scale=480:-2", str(part)])
        parts.append(part)
    _run(["ffmpeg", "-y", "-v", "error", *sum((["-i", str(p)] for p in parts), []),
          "-filter_complex", "hstack=inputs=3", str(out_path)])
    for part in parts:
        part.unlink(missing_ok=True)
    return out_path


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
    "editorial": {"font": str(FONT_DIR / "LiberationSerif-Regular.ttf"), "size": 38, "wrap": 36, "shadow": 0.3},
    "stacked":   {"font": str(FONT_DIR / "LiberationSerif-Regular.ttf"), "size": 84, "wrap": 8, "shadow": 0.3},
    "classic":   {"font": "/usr/share/fonts/opentype/inter/Inter-SemiBold.otf", "size": 60, "wrap": 22, "shadow": 0.55},
}

# Colour looks. "natural" keeps real colour (blue calipers, deep blacks), slightly low exposure.
GRADES = {
    "natural": "eq=contrast=1.08:brightness=-0.045:saturation=1.1:gamma=0.95",
    "moody": "eq=contrast=1.08:brightness=-0.03:saturation=0.82,vignette=PI/5",
    "none": None,      # as filmed (just converted from iPhone HDR)
    # Filters
    "warm": "colorbalance=rm=0.06:gm=0.01:bm=-0.06:rh=0.03:bh=-0.04,eq=saturation=1.08:contrast=1.04",
    "cool": "colorbalance=rm=-0.04:bm=0.06:bh=0.03,eq=saturation=0.95:contrast=1.06",
    "punchy": "eq=contrast=1.16:saturation=1.22:brightness=-0.02",
    "film": "curves=all='0/0.05 0.5/0.48 1/0.95',colorbalance=rs=0.03:bh=-0.03,eq=saturation=0.88",
    "mono": "hue=s=0,eq=contrast=1.12:brightness=-0.02",
    "match": None,  # copy the colours of my own posted reels (needs a reference, see match_look)
}


PCTS = (0.02, 0.10, 0.25, 0.50, 0.75, 0.90, 0.98)


def look_stats(frames_rgb):
    """Brightness curve (luma percentiles) and colourfulness of some raw RGB24 frames."""
    lumas, chroma = [], []
    for raw in frames_rgb:
        for i in range(0, len(raw) - 2, 3):
            r, g, b = raw[i], raw[i + 1], raw[i + 2]
            lumas.append(0.299 * r + 0.587 * g + 0.114 * b)
            chroma.append(max(r, g, b) - min(r, g, b))
    lumas.sort()
    return {"luma": [round(lumas[int(p * (len(lumas) - 1))], 1) for p in PCTS],
            "chroma": round(sum(chroma) / max(len(chroma), 1), 2)}


def _clip_frames(clip, start, length, n=6):
    out = []
    for i in range(n):
        t = start + length * (i + 0.5) / n
        raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.2f}", "-i", str(clip), "-frames:v", "1",
                              "-vf", f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},scale=90:160",
                              "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True).stdout
        if len(raw) == 90 * 160 * 3:
            out.append(raw)
    return out


def match_look(clip, start, length, reference, strength=0.8):
    """A colour filter that moves this clip towards the look of my own posted reels.

    reference = {"frames": [look_stats(frame), ...]} from my reels. Only the reference frames
    closest in brightness to this clip are used, so an outdoor walk-up is matched against
    my outdoor reels and an interior shot against my interior reels. Then the brightness
    curve is matched point by point (shadows, mids, highlights) and colourfulness after it.
    """
    mine = look_stats(_clip_frames(clip, start, length))
    frames = sorted(reference["frames"], key=lambda f: abs(f["luma"][3] - mine["luma"][3]) + abs(f["luma"][5] - mine["luma"][5]))
    near = frames[: max(4, len(frames) // 4)]
    ref_luma = [sum(f["luma"][i] for f in near) / len(near) for i in range(len(PCTS))]
    ref_chroma = sum(f["chroma"] for f in near) / len(near)
    points = ["0/0"]
    last_x, last_y = 0.0, 0.0
    for x, y in zip(mine["luma"], ref_luma):
        x, y = x / 255, (x + strength * (y - x)) / 255
        if x > last_x + 0.01 and y >= last_y:
            points.append(f"{x:.3f}/{y:.3f}")
            last_x, last_y = x, y
    points.append("1/1")
    sat = 1 + strength * (ref_chroma / max(mine["chroma"], 1) - 1)
    return f"curves=master='{' '.join(points)}',eq=saturation={max(0.7, min(sat, 1.15)):.2f}"


def adjust_filter(adjust):
    """Your own tweaks on top of the look: each value runs from -100 to 100 (0 = unchanged)."""
    if not adjust:
        return None
    b, c, s, w = (float(adjust.get(k) or 0) / 100 for k in ("brightness", "contrast", "saturation", "warmth"))
    parts = []
    if b or c or s:
        parts.append(f"eq=brightness={b * 0.15:.3f}:contrast={1 + c * 0.35:.3f}:saturation={max(0, 1 + s * 0.6):.3f}")
    if w:
        parts.append(f"colorbalance=rm={w * 0.12:.3f}:gm={w * 0.02:.3f}:bm={-w * 0.12:.3f}"
                     f":rh={w * 0.06:.3f}:bh={-w * 0.06:.3f}")
    return ",".join(parts) or None


def build_reference(videos, per_video=3):
    """A colour reference from my own posted reels, for match_look."""
    frames = []
    for v in videos:
        duration, _ = probe(v)
        for raw in _clip_frames(v, 0, max(duration - 0.5, 1), n=per_video):
            frames.append(look_stats([raw]))
    return {"frames": frames}


def text_lines(caption, look):
    """The text's lines and font size. layout: "auto" (wrap long lines), "one" (one line, shrunk to fit if needed),
    or your own breaks written as " | " in the text. text_scale makes it bigger or smaller."""
    style = TEXT_STYLES[look.get("text_style", "editorial")]
    size = int((look.get("font_size") or style["size"]) * float(look.get("text_scale") or 1))
    text = clean_text(caption)
    if "|" in text:
        lines = [part.strip() for part in text.split("|") if part.strip()]
    elif look.get("layout") == "one":
        lines = [text]
    else:
        lines = textwrap.wrap(text, width=int(style["wrap"] * style["size"] / size)) or [""]
    widest = max(len(line) for line in lines) if lines else 0
    if widest * size * 0.5 > W * 0.88:  # rough width of a serif line: keep it inside the frame
        size = int(W * 0.88 / (widest * 0.5))
    return lines, size


def _text_filters(caption, look):
    style = TEXT_STYLES[look.get("text_style", "editorial")]
    font = _font(look.get("font") or style["font"])
    lines, size = text_lines(caption, look)
    line_h = int(size * 1.18)
    # Never let the text slip into the parts Instagram covers.
    pos = min(max(float(look["text_position"]), SAFE_TOP), SAFE_BOTTOM - len(lines) * line_h / H)
    top = int(H * pos)
    strength = look.get("shadow") or style["shadow"]
    shadow = f":shadowcolor=black@{strength}:shadowx=1:shadowy=2" if strength else ""
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
    grade_name = look.get("grade") or ("moody" if look.get("moody_grade") else "natural")
    if grade_name == "match" and look.get("reference"):
        grade = match_look(clip, start, length, look["reference"])
    else:
        grade = GRADES.get(grade_name, GRADES["natural"])

    _, has_audio = probe(clip)
    mode = audio_cfg["mode"]
    track = None
    if mode in ("music", "mix"):
        chosen = audio_cfg.get("track")
        track = Path(audio_cfg["folder"]) / chosen if chosen else pick_track(audio_cfg["folder"])
        if track is None or not track.exists():
            print(f"  (no music track found in {audio_cfg['folder']}/, keeping original sound)")
            track, mode = None, "original"

    cmd = ["ffmpeg", "-y", "-v", "error", "-threads", THREADS, "-ss", f"{start:.2f}", "-t", f"{length:.2f}", "-i", str(clip)]
    video = f"[0:v]{frame},setpts=PTS-STARTPTS[base]"
    last = "base"
    n = 1
    if broll:
        at, dur = float(broll["at"]), float(broll["seconds"])
        cmd += ["-ss", f"{float(broll.get('start', 0)):.2f}", "-t", f"{dur:.2f}", "-i", str(broll["clip"])]
        video += (f";[{n}:v]{frame},setpts=PTS-STARTPTS+{at}/TB[br]"
                  f";[base][br]overlay=enable='between(t,{at},{at + dur})':eof_action=pass[ov]")
        last, n = "ov", n + 1
    post = [f for f in [grade, adjust_filter(look.get("adjust")), *_text_filters(caption, look)] if f]
    video += f";[{last}]{','.join(post)}[v]"

    fade = f"afade=t=out:st={max(length - 0.6, 0):.2f}:d=0.6"
    broll_sound = ""
    if broll and not broll.get("silent", True) and probe(broll["clip"])[1]:
        # B-roll set to keep its own sound: lay it over the main sound while it's on screen.
        ms = int(float(broll["at"]) * 1000)
        broll_sound = f";[1:a]adelay={ms}|{ms},apad[bra]"
    if mode == "original":
        if has_audio and broll_sound:
            audio = f"{broll_sound};[0:a][bra]amix=inputs=2:duration=first:normalize=0,{fade}[a]"
        else:
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
    cmd += ["-t", f"{length:.2f}", "-c:v", "libx264", "-preset", "fast", "-crf", "20", "-threads", THREADS, "-x264-params", "rc-lookahead=20", *SDR_TAGS,
            "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-ar", "44100",
            "-movflags", "+faststart", str(tmp)]
    _run(cmd)
    # Re-mux to drop the H.264 edit list, which makes some players show a black first frame.
    _run(["ffmpeg", "-y", "-v", "error", "-fflags", "+genpts+igndts", "-i", str(tmp),
          "-c", "copy", "-movflags", "+faststart", str(out_path)])
    tmp.unlink(missing_ok=True)
    return track
