"""ReelBot commands. Run `python -m reelbot --help`."""

import argparse
import json
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path

from . import competitors, editor, stats
from .settings import APPROVED, POSTED, REVIEW, ROOT, load_config


def cmd_stats(cfg, args):
    if args.refresh:
        rows = stats.refresh(args.period)
        print(f"Pulled {len(rows)} posts from Windsor.\n")
    print(stats.summary(stats.load()))


def cmd_research(cfg, args):
    print("Reading competitor accounts…")
    posts = competitors.refresh(cfg["competitors"], cfg["posting"]["graph_api_version"])
    print(f"\nSaved {len(posts)} competitor reels. Best performers:")
    for p in competitors.top_posts(10):
        print(f"  {p['likes_per_1k_followers']:>7}  @{p['account']}: {p['caption'][:70]!r}")


def cmd_make(cfg, args):
    clips_cfg = cfg["clips"]
    inbox = ROOT / clips_cfg["inbox_dir"]
    done = inbox / "done"
    clips = sorted(p for p in inbox.iterdir() if p.suffix.lower() in editor.VIDEO_EXTS)
    if not clips:
        print(f"No clips in {inbox}/. Drop some .mp4/.mov files in there.")
        return
    REVIEW.mkdir(parents=True, exist_ok=True)
    done.mkdir(exist_ok=True)
    count = clips_cfg["variants_per_clip"]

    for clip in clips:
        print(f"\n▶ {clip.name}")
        duration, has_audio = editor.probe(clip)
        length = min(clips_cfg["reel_seconds"], duration)
        start = 0.0
        if clips_cfg["pick_moment"] == "loudest" and has_audio:
            start = editor.loudest_start(clip, duration, length)
        print(f"  using {start:.1f}s → {start + length:.1f}s of {duration:.1f}s")

        notes_file = clip.with_suffix(".txt")
        notes = notes_file.read_text().strip() if notes_file.exists() else clip.stem.replace("_", " ")

        if args.captions:
            captions = [{"text": t.strip(), "angle": "manual"} for t in args.captions.split("|")]
        else:
            from .captions import write_captions  # only needs the Anthropic key when used
            frame = editor.extract_frame(clip, start + length / 2, REVIEW / f".{clip.stem}.jpg")
            captions = write_captions(cfg["niche"], frame, notes, count)
            frame.unlink(missing_ok=True)

        for i, cap in enumerate(captions, 1):
            out = REVIEW / f"{clip.stem}__v{i}.mp4"
            track = editor.render(clip, out, cap["text"], start, length, cfg["look"], cfg["audio"])
            meta = {"source": clip.name, "caption": cap["text"], "angle": cap["angle"],
                    "start": round(start, 2), "seconds": round(length, 2),
                    "audio": track.name if track else "original"}
            out.with_suffix(".json").write_text(json.dumps(meta, ensure_ascii=False, indent=1))
            print(f"  ✓ v{i} [{cap['angle']}] “{cap['text']}”")

        shutil.move(str(clip), done / clip.name)
        if notes_file.exists():
            shutil.move(str(notes_file), done / notes_file.name)

    print(f"\nDone. Watch them in {REVIEW.relative_to(ROOT)}/ then run: python -m reelbot approve all")


def cmd_approve(cfg, args):
    APPROVED.mkdir(parents=True, exist_ok=True)
    videos = sorted(REVIEW.glob("*.mp4")) if REVIEW.exists() else []
    if args.name != "all":
        videos = [v for v in videos if v.stem == args.name or v.name == args.name]
    for v in videos:
        for f in (v, v.with_suffix(".json")):
            if f.exists():
                shutil.move(str(f), APPROVED / f.name)
        print(f"  ✓ approved {v.name}")
    if not videos:
        print("Nothing to approve.")


def cmd_post(cfg, args):
    from .publisher import post_reel

    posting = cfg["posting"]
    source = APPROVED if posting["require_approval"] else REVIEW
    videos = sorted(source.glob("*.mp4")) if source.exists() else []
    videos = videos[: posting["max_posts_per_run"]]
    if not videos:
        print(f"Nothing ready to post in {source.relative_to(ROOT)}/.")
        return
    POSTED.mkdir(parents=True, exist_ok=True)
    for n, video in enumerate(videos):
        meta_file = video.with_suffix(".json")
        meta = json.loads(meta_file.read_text()) if meta_file.exists() else {"caption": ""}
        caption = " ".join(x for x in (meta["caption"], posting.get("hashtags", "")) if x)
        if args.dry_run:
            print(f"  (dry run) would post {video.name}: {caption!r}")
            continue
        print(f"  posting {video.name}…")
        media_id = post_reel(video, caption, posting)
        meta.update(media_id=media_id, posted_at=datetime.now(timezone.utc).isoformat())
        meta_file.write_text(json.dumps(meta, ensure_ascii=False, indent=1))
        for f in (video, meta_file):
            shutil.move(str(f), POSTED / f.name)
        print(f"  ✓ live as trial reel (media id {media_id})")
        if n < len(videos) - 1:
            time.sleep(posting["minutes_between_posts"] * 60)


def cmd_run(cfg, args):
    """The whole loop: learn from latest stats, edit new clips, post what's ready."""
    try:
        cmd_stats(cfg, argparse.Namespace(refresh=True, period="last_30d"))
    except SystemExit as e:
        print(f"(skipping stats refresh: {e})")
    cmd_make(cfg, argparse.Namespace(captions=None))
    cmd_post(cfg, argparse.Namespace(dry_run=False))


def main():
    parser = argparse.ArgumentParser(prog="reelbot", description="Clips in → trial reels out.")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("stats", help="show what's working on your account")
    p.add_argument("--refresh", action="store_true", help="pull fresh numbers from Windsor first")
    p.add_argument("--period", default="last_30d")
    p.set_defaults(func=cmd_stats)

    sub.add_parser("research", help="study competitor accounts").set_defaults(func=cmd_research)

    p = sub.add_parser("make", help="edit every clip in inbox/ into captioned reels")
    p.add_argument("--captions", help='skip the AI and use your own, e.g. "Caption one|Caption two"')
    p.set_defaults(func=cmd_make)

    p = sub.add_parser("approve", help="OK videos in output/review for posting")
    p.add_argument("name", nargs="?", default="all")
    p.set_defaults(func=cmd_approve)

    p = sub.add_parser("post", help="post approved videos as trial reels")
    p.add_argument("--dry-run", action="store_true", help="show what would post without posting")
    p.set_defaults(func=cmd_post)

    sub.add_parser("run", help="stats → make → post, all in one").set_defaults(func=cmd_run)

    args = parser.parse_args()
    args.func(load_config(), args)


if __name__ == "__main__":
    main()
