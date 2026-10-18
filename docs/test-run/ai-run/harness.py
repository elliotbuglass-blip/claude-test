"""Test harness: ReelBot web app in-process with posting disabled and Claude spend tracked."""
import json, os, sys, threading, time
from pathlib import Path
SP = Path(__file__).parent
os.environ.setdefault("REELBOT_STORAGE", str(SP / "run" / "storage"))
sys.path.insert(0, "/home/user/claude-test")

import reelbot.publisher as publisher
def _no_post(*a, **k):
    raise RuntimeError("Posting disabled in the test run")
publisher.post_reel = _no_post

from reelbot import settings, vision
from reelbot.app import brain
PRICE_IN, PRICE_OUT, CAP = 4.0, 20.0, 4.6
SPEND = SP / "run" / "spend.json"
lock = threading.Lock()
def _load():
    return json.loads(SPEND.read_text()) if SPEND.exists() else {"calls": 0, "in": 0, "out": 0, "usd": 0.0, "by": {}}
_orig = settings.claude
def tracked_claude():
    client = _orig()
    create = client.beta.messages.create
    def wrapped(**kw):
        if _load()["usd"] >= CAP:
            raise RuntimeError(f"Test spend cap ${CAP} reached")
        r = create(**kw)
        u = r.usage
        tin = u.input_tokens + (u.cache_creation_input_tokens or 0) + (u.cache_read_input_tokens or 0)
        cost = tin * PRICE_IN / 1e6 + u.output_tokens * PRICE_OUT / 1e6
        import inspect
        caller = next((f.function for f in inspect.stack()[1:] if f.function not in ("wrapped", "_ask")), "?")
        with lock:
            s = _load(); s["calls"] += 1; s["in"] += tin; s["out"] += u.output_tokens; s["usd"] = round(s["usd"] + cost, 4)
            b = s["by"].setdefault(caller, [0, 0.0]); b[0] += 1; b[1] = round(b[1] + cost, 4)
            SPEND.write_text(json.dumps(s, indent=1))
        return r
    client.beta.messages.create = wrapped
    return client
brain.claude = tracked_claude
vision.claude = tracked_claude

import uvicorn
from reelbot.app import db, jobs, import_drive
for k, v in {"mode": "review", "reels_per_clip": 2}.items():
    db.set_setting(k, v)

def go():
    time.sleep(5)
    if os.environ.get("IMPORT") == "1":
        print("IMPORT:", import_drive.run(), flush=True)
    for name in filter(None, os.environ.get("REMAKE", "").split(",")):
        jobs.submit(f"remake {name}", jobs.make_reels, db.one("SELECT id FROM clips WHERE filename = ?", name)["id"])
    if os.environ.get("RETEXT"):
        names = os.environ["RETEXT"].split(",")
        for r in db.q("SELECT r.id FROM reels r JOIN clips c ON c.id = r.clip_id WHERE c.filename IN (%s)" % ",".join("?" * len(names)), *names):
            db.update("reels", r["id"], text_position=None, text_reason=None, text_spots=None, status="rendering")
            jobs.submit("re-place text", jobs.render_reel, r["id"])
    if os.environ.get("RETEST") == "1":
        # 1) fresh plans for clips that had problems, 2) redo the text spot on every older reel
        old = [r["id"] for r in db.q("SELECT id FROM reels WHERE status = 'draft'")]
        for name in ("IMG_8194.MOV", "IMG_8958.MOV", "IMG_9194.mov"):
            clip = db.one("SELECT id FROM clips WHERE filename = ?", name)
            jobs.submit(f"remake {name}", jobs.make_reels, clip["id"])
        for rid in old:
            db.update("reels", rid, text_position=None, text_reason=None, text_spots=None, status="rendering")
            jobs.submit("re-place text", jobs.render_reel, rid)
threading.Thread(target=go, daemon=True).start()
uvicorn.run("reelbot.app.web:app", host="127.0.0.1", port=8000)
