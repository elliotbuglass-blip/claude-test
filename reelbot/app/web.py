"""The ReelBot website. Run locally with:  python -m reelbot.app  (then open http://localhost:8000)"""

import contextlib
import hashlib
import hmac
import json
import os
import shutil
import statistics
from datetime import datetime, timedelta
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

from .. import editor
from ..settings import env
from . import db, jobs

HERE = Path(__file__).parent
templates = Environment(loader=FileSystemLoader(HERE / "templates"), autoescape=select_autoescape())


def _fmt_time(value):
    if not value:
        return ""
    d = datetime.fromisoformat(value)
    today = jobs.local_now().date()
    day = "Today" if d.date() == today else "Tomorrow" if d.date() == today + timedelta(days=1) else d.strftime("%a %d %b")
    return f"{day} {d:%H:%M}"


templates.filters["when"] = _fmt_time
templates.filters["num"] = lambda v: f"{v:,}" if isinstance(v, (int, float)) else "–"


def page(name, request, **ctx):
    ctx.update(request=request, nav=request.url.path, busy=jobs.busy(), mode=jobs.setting("mode"),
               events=db.q("SELECT * FROM events ORDER BY id DESC LIMIT 6"))
    return HTMLResponse(templates.get_template(name).render(**ctx))


# --------------------------------------------------------------------------- login (one password for now)

def _token():
    secret = os.environ.get("APP_PASSWORD", "")
    return hmac.new(secret.encode(), b"reelbot", hashlib.sha256).hexdigest()


class Auth(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        open_paths = ("/login", "/static", "/health")
        if os.environ.get("APP_PASSWORD") and not request.url.path.startswith(open_paths):
            if not hmac.compare_digest(request.cookies.get("rb", ""), _token()):
                return RedirectResponse("/login", 303)
        return await call_next(request)


async def login(request: Request):
    error = ""
    if request.method == "POST":
        form = await request.form()
        if hmac.compare_digest(form.get("password", ""), os.environ.get("APP_PASSWORD", "")):
            resp = RedirectResponse("/", 303)
            resp.set_cookie("rb", _token(), max_age=60 * 60 * 24 * 90, httponly=True, samesite="lax")
            return resp
        error = "Wrong password"
    return HTMLResponse(templates.get_template("login.html").render(error=error))


# --------------------------------------------------------------------------- review

async def review(request: Request):
    reels = db.q("""SELECT r.*, c.filename FROM reels r JOIN clips c ON c.id = r.clip_id
                    WHERE r.status IN ('draft', 'rendering', 'failed') ORDER BY r.created_at DESC""")
    brolls = db.q("SELECT * FROM clips WHERE kind = 'broll' ORDER BY created_at DESC")
    return page("review.html", request, reels=reels, brolls=brolls,
                times=jobs.next_free_slots(6))


async def reel_action(request: Request):
    reel_id, action = request.path_params["id"], request.path_params["action"]
    form = await request.form()
    reel = db.one("SELECT * FROM reels WHERE id = ?", reel_id)
    if action == "approve":
        jobs.approve(reel_id, form.get("post_at") or reel["recommended_time"])
    elif action == "reject":
        db.update("reels", reel_id, status="rejected")
    elif action == "unschedule":
        db.update("reels", reel_id, status="draft", post_at=None)
    elif action == "edit":
        fields = {k: form.get(k) for k in ("on_screen_text", "post_caption", "sound_suggestion") if form.get(k) is not None}
        fields["text_position"] = None  # re-place text for the new wording
        if form.get("broll_clip"):
            fields["broll"] = json.dumps({"clip_id": form["broll_clip"], "at": float(form.get("broll_at") or 0),
                                          "seconds": float(form.get("broll_seconds") or 1.5),
                                          "start": float(form.get("broll_start") or 0)})
        elif form.get("broll_clip") == "":
            fields["broll"] = None
        db.update("reels", reel_id, status="rendering", **fields)
        jobs.submit("re-render", jobs.render_reel, reel_id)
    return RedirectResponse(request.headers.get("referer", "/"), 303)


async def thumb(request: Request):
    path = db.RENDERS_DIR / f"{request.path_params['id']}.jpg"
    return FileResponse(path, media_type="image/jpeg") if path.exists() else HTMLResponse("", 404)


async def video(request: Request):
    reel = db.one("SELECT video_path FROM reels WHERE id = ?", request.path_params["id"])
    if not reel or not reel["video_path"] or not Path(reel["video_path"]).exists():
        return HTMLResponse("Not ready", 404)
    return FileResponse(reel["video_path"], media_type="video/mp4")


# --------------------------------------------------------------------------- clips

async def clips_page(request: Request):
    clips = db.q("SELECT * FROM clips ORDER BY created_at DESC")
    for c in clips:
        c["reels"] = db.one("SELECT COUNT(*) n FROM reels WHERE clip_id = ? AND status != 'rejected'", c["id"])["n"]
    return page("clips.html", request, clips=clips)


async def upload(request: Request):
    form = await request.form()
    kind = form.get("kind") or None
    count = 0
    for f in form.getlist("files"):
        if not getattr(f, "filename", None) or Path(f.filename).suffix.lower() not in editor.VIDEO_EXTS:
            continue
        dest = db.CLIPS_DIR / f"{db.new_id()}_{Path(f.filename).name}"
        with dest.open("wb") as out:
            shutil.copyfileobj(f.file, out, 1 << 20)
        jobs.add_clip(dest, f.filename, None if kind == "auto" else kind)
        count += 1
    for f in form.getlist("music"):
        if getattr(f, "filename", None) and Path(f.filename).suffix.lower() in editor.AUDIO_EXTS:
            with (db.AUDIO_DIR / Path(f.filename).name).open("wb") as out:
                shutil.copyfileobj(f.file, out, 1 << 20)
    db.log(f"Uploaded {count} clip(s)")
    return RedirectResponse("/clips", 303)


async def clip_action(request: Request):
    clip_id, action = request.path_params["id"], request.path_params["action"]
    form = await request.form()
    if action == "kind":
        db.update("clips", clip_id, kind=form["kind"])
    elif action == "silent":
        db.update("clips", clip_id, broll_silent=1 if form.get("silent") == "1" else 0)
    elif action == "make":
        jobs.submit("make reels", jobs.make_reels, clip_id, int(form.get("n") or 3))
    elif action == "delete":
        clip = db.one("SELECT * FROM clips WHERE id = ?", clip_id)
        Path(clip["path"]).unlink(missing_ok=True)
        db.run("DELETE FROM clips WHERE id = ?", clip_id)
    return RedirectResponse("/clips", 303)


# --------------------------------------------------------------------------- schedule + results

async def schedule(request: Request):
    reels = db.q("""SELECT r.*, c.filename FROM reels r JOIN clips c ON c.id = r.clip_id
                    WHERE r.status IN ('scheduled', 'posting') ORDER BY r.post_at""")
    return page("schedule.html", request, reels=reels, times=jobs.posting_times())


async def results(request: Request):
    reels = db.q("SELECT * FROM reels WHERE status = 'posted' ORDER BY posted_at DESC")
    snaps = {}
    for s in db.q("SELECT * FROM snapshots"):
        snaps.setdefault(s["reel_id"], {})[s["hours"]] = s
    for r in reels:
        r["snaps"] = snaps.get(r["id"], {})
        latest = r["snaps"].get(72) or r["snaps"].get(48) or r["snaps"].get(24)
        r["latest"] = latest
    scored = [r for r in reels if r["snaps"].get(72) or r["snaps"].get(48)]
    summary = None
    if scored:
        views = [(r["snaps"].get(72) or r["snaps"].get(48))["views"] or 0 for r in scored]
        summary = {"reels": len(scored), "median": int(statistics.median(views)), "best": max(views)}
    return page("results.html", request, reels=reels, summary=summary)


# --------------------------------------------------------------------------- research + settings

async def research(request: Request):
    if request.method == "POST":
        form = await request.form()
        if form.get("run") == "radar":
            jobs.submit("competitor radar", jobs.run_radar)
        elif form.get("run") == "history":
            jobs.submit("refresh history", jobs.refresh_history)
        return RedirectResponse("/research", 303)
    return page("research.html", request, best=db.latest_research("best_times"), topic=db.latest_research("topic"),
                radar=db.latest_research("radar"), times=jobs.posting_times())


async def settings_page(request: Request):
    if request.method == "POST":
        form = await request.form()
        for key in ("mode", "niche", "times_mode", "text_style", "grade", "hashtags"):
            if key in form:
                db.set_setting(key, form[key])
        for key in ("posts_per_day", "reels_per_clip", "reel_seconds"):
            if form.get(key):
                db.set_setting(key, int(form[key]))
        db.set_setting("broll_silent", form.get("broll_silent") == "1")
        if form.get("post_times") is not None:
            db.set_setting("post_times", [t.strip() for t in form["post_times"].split(",") if t.strip()])
        if form.get("competitors") is not None:
            names = [n.strip().lstrip("@") for n in form["competitors"].replace(",", "\n").splitlines() if n.strip()]
            db.set_setting("competitors", [{"username": n, "notes": ""} for n in names])
        db.log("Settings saved")
        return RedirectResponse("/settings", 303)
    c = jobs.cfg()
    keys = {k: bool(env(k, required=False)) for k in ("ANTHROPIC_API_KEY", "IG_ACCESS_TOKEN", "IG_USER_ID", "APIFY_TOKEN", "APP_PASSWORD")}
    return page("settings.html", request, c=c, s={k: jobs.setting(k) for k in jobs.EDITABLE}, keys=keys,
                styles=list(editor.TEXT_STYLES), grades=list(editor.GRADES))


async def home(request: Request):
    return RedirectResponse("/review", 303)


async def health(request: Request):
    return JSONResponse({"ok": True, "queue": jobs.busy()})


routes = [
    Route("/", home), Route("/health", health),
    Route("/login", login, methods=["GET", "POST"]),
    Route("/review", review),
    Route("/reels/{id}/{action}", reel_action, methods=["POST"]),
    Route("/video/{id}.mp4", video), Route("/thumb/{id}.jpg", thumb),
    Route("/clips", clips_page), Route("/upload", upload, methods=["POST"]),
    Route("/clips/{id}/{action}", clip_action, methods=["POST"]),
    Route("/schedule", schedule), Route("/results", results),
    Route("/research", research, methods=["GET", "POST"]),
    Route("/settings", settings_page, methods=["GET", "POST"]),
    Mount("/static", StaticFiles(directory=HERE / "static"), name="static"),
]

@contextlib.asynccontextmanager
async def lifespan(app):
    jobs.start()
    yield


app = Starlette(routes=routes, middleware=[Middleware(Auth)], lifespan=lifespan)
