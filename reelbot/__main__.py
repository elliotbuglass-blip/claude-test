"""ReelBot commands. Run `python -m reelbot --help`."""

import argparse
import json
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path

from . import competitors, editor, stats, vision
from .settings import APPROVED, POSTED, REVIEW, ROOT, load_config


def cmd_stats(cfg, args):
    if args.refresh:
        rows = stats.refresh(args.period)
        print(f"Pulled {len(rows)} posts from Windsor.\n")
    if args.read_text:
        print("Reading the on-screen text of your reels…")
        stats.read_onscreen_text()
        print()
    print(stats.summary(stats.load()))


def cmd_research(cfg, args):
    from . import research

    print("Competitor Radar: pulling reels…")
    outliers = competitors.run(cfg["competitors"], cfg["radar"], use_cache=args.cached)
    print(f"\nTop outliers (on-screen hook):")
    for o in outliers[:10]:
        print(f"  {o['ratio']:>5}x  {o['views']:>10,}  @{o['account']}: “{o.get('on_screen_text') or '(no text)'}”")
    print("\nMaking sure your own on-screen hooks are read…")
    stats.read_onscreen_text()
    print("Writing the research brief…")
    brief = research.build(cfg["niche"])
    print("\nWinning patterns:")
    for p in brief["winning_patterns"]:
        print(f"  • {p['pattern']}")
    print(f"\nFull pick list: output/picklist.md")


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
        try:
            _make_one(cfg, args, clip, done, count)
        except Exception as e:  # keep going: one bad clip shouldn't stop the batch
            print(f"  ✗ skipped {clip.name}: {e}")

    print(f"\nDone. Watch them in {REVIEW.relative_to(ROOT)}/ then run: python -m reelbot approve all")


def _make_one(cfg, args, clip, done, count):
    clips_cfg = cfg["clips"]
    duration, has_audio = editor.probe(clip)
    length = min(clips_cfg["reel_seconds"], duration)
    start = 0.0
    if clips_cfg["pick_moment"] == "loudest" and has_audio:
        start = editor.loudest_start(clip, duration, length)
    print(f"  using {start:.1f}s → {start + length:.1f}s of {duration:.1f}s")

    notes_file = clip.with_suffix(".txt")
    notes = notes_file.read_text().strip() if notes_file.exists() else clip.stem.replace("_", " ")

    if args.captions:
        captions = [{"on_screen_text": t.strip(), "post_caption": t.strip(), "angle": "manual",
                     "inspired_by": ""} for t in args.captions.split("|")]
    else:
        from .captions import write_captions  # only needs the Anthropic key when used
        frame = editor.extract_frame(clip, start + length / 2, REVIEW / f".{clip.stem}.jpg")
        captions = write_captions(cfg["niche"], frame, notes, count)
        frame.unlink(missing_ok=True)

    for i, cap in enumerate(captions, 1):
        out = REVIEW / f"{clip.stem}__v{i}.mp4"
        on_screen = editor.clean_text(cap["on_screen_text"])
        track = editor.render(clip, out, on_screen, start, length, cfg["look"], cfg["audio"])
        meta = {"source": clip.name, "on_screen_text": on_screen, "caption": cap["post_caption"],
                "angle": cap["angle"], "inspired_by": cap["inspired_by"],
                "start": round(start, 2), "seconds": round(length, 2),
                "audio": track.name if track else "original"}
        out.with_suffix(".json").write_text(json.dumps(meta, ensure_ascii=False, indent=1))
        print(f"  ✓ v{i} [{cap['angle']}] “{on_screen}”")

    shutil.move(str(clip), done / clip.name)
    if notes_file.exists():
        shutil.move(str(notes_file), done / notes_file.name)


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
        media_id = post_reel(video, caption, posting, slot=n)
        meta.update(media_id=media_id, posted_at=datetime.now(timezone.utc).isoformat())
        if not str(media_id).startswith("metricool:"):
            vision.remember(f"me:{media_id}", meta.get("on_screen_text", ""))  # no need to re-read it later
        meta_file.write_text(json.dumps(meta, ensure_ascii=False, indent=1))
        for f in (video, meta_file):
            shutil.move(str(f), POSTED / f.name)
        print(f"  ✓ live as trial reel (media id {media_id})")
        if posting.get("backend") != "metricool" and n < len(videos) - 1:
            time.sleep(posting["minutes_between_posts"] * 60)


def cmd_run(cfg, args):
    """The whole loop: learn from latest stats, edit new clips, post what's ready."""
    try:
        cmd_stats(cfg, argparse.Namespace(refresh=True, period="last_30d", read_text=True))
    except SystemExit as e:
        print(f"(skipping stats refresh: {e})")
    cmd_make(cfg, argparse.Namespace(captions=None))
    cmd_post(cfg, argparse.Namespace(dry_run=False))


def cmd_pull(cfg, args):
    from . import session
    session.pull(cfg)


def cmd_radar(cfg, args):
    from . import session
    session.radar(cfg)


def cmd_topic(cfg, args):
    from . import session
    session.topic(cfg, args.hashtags, per_tag=args.per_tag)


def cmd_schedule(cfg, args):
    from . import autopilot
    autopilot.schedule(cfg, args.plan)


def cmd_slots(cfg, args):
    from . import autopilot
    print("\n".join(autopilot.next_slots(cfg, args.count)))


def cmd_post_due(cfg, args):
    from . import autopilot
    autopilot.post_due(cfg, dry_run=args.dry_run)


def cmd_results(cfg, args):
    from . import autopilot
    autopilot.results(cfg)


def cmd_cloud(cfg, args):
    from . import cloud
    cloud.run(cfg, args.task)


def main():
    parser = argparse.ArgumentParser(prog="reelbot", description="Clips in → trial reels out.")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("stats", help="show what's working on your account")
    p.add_argument("--refresh", action="store_true", help="pull fresh numbers from Windsor first")
    p.add_argument("--period", default="last_30d")
    p.add_argument("--read-text", action="store_true", help="read the on-screen text of your reels")
    p.set_defaults(func=cmd_stats)

    p = sub.add_parser("research", help="competitor radar + research brief (weekly)")
    p.add_argument("--cached", action="store_true", help="re-score last pull without spending credits")
    p.set_defaults(func=cmd_research)

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

    sub.add_parser("pull", help="download new clips from your Google Drive folder").set_defaults(func=cmd_pull)
    sub.add_parser("radar", help="find competitor outliers + save frames (Claude reads them)").set_defaults(func=cmd_radar)

    p = sub.add_parser("topic", help="research a topic: top reels + sounds for some hashtags")
    p.add_argument("hashtags", nargs="+", help="e.g. astonmartin db12 supercar")
    p.add_argument("--per-tag", type=int, default=40)
    p.set_defaults(func=cmd_topic)

    p = sub.add_parser("schedule", help="autopilot: add a plan of reels to the posting queue")
    p.add_argument("plan", help="path to a plan JSON, e.g. data/plan.json")
    p.set_defaults(func=cmd_schedule)

    p = sub.add_parser("slots", help="autopilot: tomorrow's posting times")
    p.add_argument("count", type=int, nargs="?", default=5)
    p.set_defaults(func=cmd_slots)

    p = sub.add_parser("post-due", help="autopilot: render + post queued reels that are due")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(func=cmd_post_due)

    sub.add_parser("results", help="autopilot: fetch results for every reel ReelBot posted").set_defaults(func=cmd_results)

    p = sub.add_parser("cloud", help="run on GitHub using your Google Drive folder")
    p.add_argument("--task", default="daily", choices=["daily", "research", "make-only", "post-only"])
    p.set_defaults(func=cmd_cloud)

    args = parser.parse_args()
    args.func(load_config(), args)


if __name__ == "__main__":
    main()
