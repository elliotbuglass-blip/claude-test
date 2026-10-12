"""Runs ReelBot on GitHub's computers, using Google Drive as the place you drop clips and pick up videos.

Your Drive "ReelBot" folder:
    inbox/       ← you drop raw clips here (optionally a same-named .txt with notes)
    review/      → finished videos appear here; the hook + caption are in each file's description
    approved/    ← drag the ones you like here; the next run posts them
    posted/      → posted videos end up here
    used-clips/  → raw clips that have been edited
    audio/       ← optional music tracks (for audio mode "music" or "mix")
    data/        the robot's memory (stats, on-screen text, research). Leave it alone.
    picklist.md  → the weekly research pick list
"""

import argparse
import json

from . import editor
from .drive import Drive, meta_from_description
from .settings import APPROVED, DATA, OUTPUT, POSTED, REVIEW, ROOT, env

FOLDERS = ["inbox", "review", "approved", "posted", "used-clips", "audio", "data"]


def run(cfg, task):
    from .__main__ import cmd_make, cmd_post, cmd_research, cmd_stats

    drive = Drive()
    f = drive.ensure_folders(env("DRIVE_FOLDER_ID"), FOLDERS)
    print("Loading the robot's memory from Drive…")
    drive.sync_down(f["data"], DATA)
    drive.sync_down(f["audio"], ROOT / cfg["audio"]["folder"])

    try:
        if task == "research":
            cmd_research(cfg, argparse.Namespace(cached=False))
            drive_picklist(drive, env("DRIVE_FOLDER_ID"))
            return

        if task in ("daily", "make-only"):
            try:
                cmd_stats(cfg, argparse.Namespace(refresh=True, period="last_30d", read_text=True))
            except SystemExit as e:
                print(f"(skipping stats: {e})")
            make_from_inbox(drive, f, cfg)

        if task in ("daily", "post-only"):
            post_approved(drive, f, cfg)
    finally:
        print("Saving the robot's memory to Drive…")
        drive.sync_up(DATA, f["data"])


def make_from_inbox(drive, f, cfg):
    from .__main__ import cmd_make

    inbox = ROOT / cfg["clips"]["inbox_dir"]
    clips = [x for x in drive.list(f["inbox"])
             if x["name"].lower().endswith(tuple(editor.VIDEO_EXTS) + (".txt",))]
    if not clips:
        print("Drive inbox is empty — nothing to edit.")
        return
    for c in clips:
        drive.download(c["id"], inbox / c["name"])

    cmd_make(cfg, argparse.Namespace(captions=None))

    # Upload finished videos, with their hook/caption saved in the Drive file description.
    for video in sorted(REVIEW.glob("*.mp4")):
        meta_file = video.with_suffix(".json")
        description = meta_file.read_text() if meta_file.exists() else None
        drive.upload(video, f["review"], description=description)
        print(f"  ↑ review/{video.name}")

    # Clips that were edited successfully were moved to inbox/done locally.
    done = {p.name for p in (inbox / "done").glob("*")}
    for c in clips:
        if c["name"] in done:
            drive.move(c["id"], f["inbox"], f["used-clips"])


def post_approved(drive, f, cfg):
    from .__main__ import cmd_post

    approved = [x for x in drive.list(f["approved"]) if x["name"].lower().endswith(".mp4")]
    if not approved:
        print("Nothing in Drive approved/ — nothing to post.")
        return
    cfg["posting"]["require_approval"] = True  # in the cloud, approval = moving to approved/
    APPROVED.mkdir(parents=True, exist_ok=True)
    for v in approved:
        drive.download(v["id"], APPROVED / v["name"])
        meta = meta_from_description(v.get("description"))
        meta.setdefault("caption", meta.get("on_screen_text", ""))
        (APPROVED / v["name"]).with_suffix(".json").write_text(json.dumps(meta, ensure_ascii=False))

    cmd_post(cfg, argparse.Namespace(dry_run=False))

    for v in approved:
        posted_meta = (POSTED / v["name"]).with_suffix(".json")
        if posted_meta.exists():
            drive.move(v["id"], f["approved"], f["posted"], description=posted_meta.read_text())


def drive_picklist(drive, root_id):
    picklist = OUTPUT / "picklist.md"
    if picklist.exists():
        existing = {x["name"]: x["id"] for x in drive.list(root_id)}
        drive.upload(picklist, root_id, replace_id=existing.get("picklist.md"))
        print("  ↑ picklist.md")
