"""Import clips from the Google Drive folder into the app: "Main" and "B-roll" subfolders.

A same-named .txt next to a clip (IMG_8960.txt) is the creator's description of it.
Clips already in the app (same file name) are skipped, so this is safe to run again.

Call run() from inside the running app: each clip is queued for analysis on the app's worker.
"""

from pathlib import Path

from .. import session
from . import db, jobs

KINDS = {"main": "main", "b-roll": "broll", "broll": "broll"}


def run(cfg=None):
    cfg = cfg or jobs.cfg()
    have = {r["filename"] for r in db.q("SELECT filename FROM clips")}
    added = []
    for folder in session.list_folder(session.folder_id(cfg)):
        kind = KINDS.get(folder["name"].strip().lower())
        if not kind or not folder["mimeType"].endswith("folder"):
            continue
        files = session.list_folder(folder["id"])
        notes = {Path(f["name"]).stem: f for f in files if f["name"].lower().endswith(".txt")}
        for f in files:
            name = f["name"]
            if not name.lower().endswith(session.VIDEO_EXTS) or name in have:
                continue  # skips notes, and duplicates of a clip already imported
            have.add(name)
            path = db.CLIPS_DIR / f"{db.new_id()}{Path(name).suffix.lower()}"
            session.download(f["id"], path)
            note = notes.get(Path(name).stem)
            description = ""
            if note:
                with session._drive_get(f"{session.DRIVE}/{note['id']}", alt="media") as r:
                    description = r.content.decode("utf-8", "replace").replace("\r\n", "\n").strip()
            added.append(jobs.add_clip(path, name, kind=kind, description=description))
            db.log(f"Imported {name} from Drive ({kind}{', with your note' if description else ''})")
    return added
