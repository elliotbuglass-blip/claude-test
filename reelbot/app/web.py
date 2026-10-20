"""The ReelBot website. Run locally with:  python -m reelbot.app  (then open http://localhost:8000)"""

import asyncio
import contextlib
import hashlib
import hmac
import json
import os
import shutil
import statistics
from collections import Counter
from datetime import datetime, timedelta, timezone
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
from ..settings import claude_key, env
from . import brain, connect, db, jobs, links

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
templates.globals["SOURCE_LABELS"] = jobs.SOURCE_LABELS
templates.filters["fromjson"] = lambda v: json.loads(v) if v else None


def initials():
    name = connect.status().get("username") or ""
    return name.replace(".", " ").replace("_", " ").title().replace(" ", "")[:2] or "Me"


def page(name, request, **ctx):
    ctx.setdefault("initials", initials())
    ctx.update(request=request, nav=request.url.path, busy=jobs.busy(), mode=jobs.setting("mode"),
               paused=db.get_setting("posting_paused"),
               events=db.q("SELECT * FROM events ORDER BY id DESC LIMIT 6"))
    return HTMLResponse(templates.get_template(name).render(**ctx))


# --------------------------------------------------------------------------- login (one password for now)

def _token():
    secret = os.environ.get("APP_PASSWORD", "")
    return hmac.new(secret.encode(), b"reelbot", hashlib.sha256).hexdigest()


class Auth(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        open_paths = ("/login", "/static", "/health", "/public/")  # /public/ links are signed and expire
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

def look_note(grade, look):
    if grade == "match":
        return (f"Matched to the colours of your last {look['reels']} reels" if look else
                "Matched to the colours of your recent reels") + \
               " (shadows, mid-tones and highlights copied from the closest-looking scenes, then colour strength)"
    return {"natural": "Natural: real colour, slightly low exposure", "moody": "Moody: desaturated with a vignette",
            "none": "No colour change"}.get(grade, grade)


async def review(request: Request):
    reels = db.q("""SELECT r.*, c.filename, c.duration AS clip_seconds FROM reels r JOIN clips c ON c.id = r.clip_id
                    WHERE r.status IN ('draft', 'rendering', 'failed') ORDER BY r.created_at DESC""")
    look = db.latest_research("look")
    for r in reels:
        r["look_note"] = look_note(r["grade"], look)
    brolls = db.q("SELECT * FROM clips WHERE kind = 'broll' ORDER BY created_at DESC")
    return page("review.html", request, reels=reels, brolls=brolls, hashtags=jobs.cfg()["posting"].get("hashtags", ""),
                times=jobs.next_free_slots(6))


async def reel_action(request: Request):
    reel_id, action = request.path_params["id"], request.path_params["action"]
    form = await request.form()
    reel = db.one("SELECT * FROM reels WHERE id = ?", reel_id)
    if action == "approve":
        when = form.get("post_at") or reel["recommended_time"]
        if when == "now":
            jobs.post_now(reel_id)
        else:
            jobs.approve(reel_id, form.get("custom_at") if when == "custom" and form.get("custom_at") else when)
    elif action == "spot":
        jobs.pick_text_spot(reel_id, int(form.get("spot") or 0))
    elif action == "retry":
        db.update("reels", reel_id, status="rendering", error=None)
        jobs.submit("re-render", jobs.render_reel, reel_id)
    elif action == "postnow":
        jobs.post_now(reel_id)
    elif action in ("reject", "remove"):
        db.update("reels", reel_id, status="rejected", post_at=None)
        if action == "remove":
            db.log(f"Removed “{reel['on_screen_text']}” from the calendar")
    elif action == "reschedule":
        if form.get("post_at"):
            jobs.approve(reel_id, form["post_at"])
    elif action == "review":
        jobs.submit("learn from results", jobs.review_reel, reel_id)
    elif action == "remake":
        ok, why = jobs.remake_allowed(reel_id)
        if ok:
            jobs.submit("remake reel", jobs.remake, reel_id)
        else:
            db.log(f"Remake skipped: {why}")
    elif action == "unschedule":
        db.update("reels", reel_id, status="draft", post_at=None)
    elif action == "trim":
        db.update("reels", reel_id, status="rendering")
        jobs.submit("re-cut reel", jobs.trim, reel_id, float(form.get("start") or 0), float(form.get("length") or 8),
                    form.get("whole") == "1")
    elif action == "caption":
        db.update("reels", reel_id, post_caption=(form.get("post_caption") or "").strip())
        return RedirectResponse(request.headers.get("referer", "/review"), 303)
    elif action == "colour":
        adjust = {k: int(form.get(k) or 0) for k in ("brightness", "contrast", "saturation", "warmth")}
        db.update("reels", reel_id, grade=form.get("grade") or reel["grade"], adjust=json.dumps(adjust), status="rendering")
        jobs.submit("re-colour", jobs.render_reel, reel_id)
    elif action == "chat":
        if (form.get("message") or "").strip():
            db.update("reels", reel_id, status="rendering")
            jobs.submit("change reel", jobs.chat_edit, reel_id, form["message"].strip())
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


async def rerender_all(request: Request):
    db.run("UPDATE reels SET status = 'rendering' WHERE status IN ('draft', 'failed')")
    jobs.submit("re-make all reels", jobs.rerender_all)
    return RedirectResponse("/review", 303)


async def thumb(request: Request):
    name = request.path_params["id"]
    path = db.RENDERS_DIR / f"{name}.jpg"
    return FileResponse(path, media_type="image/jpeg") if path.exists() else HTMLResponse("", 404)


def clip_thumb(request):
    """A still from a clip for the library (made once, then kept)."""
    clip = db.one("SELECT path FROM clips WHERE id = ?", request.path_params["id"])
    out = db.RENDERS_DIR / f"clip_{request.path_params['id']}.jpg"
    if clip and not out.exists() and Path(clip["path"]).exists():
        try:
            editor.extract_frame(clip["path"], 1.0, out)
        except Exception:
            pass
    return FileResponse(out, media_type="image/jpeg") if out.exists() else HTMLResponse("", 404)


def thumb_spots(request):
    path = db.RENDERS_DIR / f"{request.path_params['id']}_spots.jpg"
    return FileResponse(path, media_type="image/jpeg") if path.exists() else HTMLResponse("", 404)


async def public_video(request: Request):
    """The reel for Instagram to download while publishing: only with a valid, unexpired signed link."""
    reel_id = request.path_params["id"]
    if not links.valid(reel_id, request.query_params.get("e"), request.query_params.get("s")):
        return HTMLResponse("Link expired", 403)
    reel = db.one("SELECT video_path FROM reels WHERE id = ?", reel_id)
    if not reel or not reel["video_path"] or not Path(reel["video_path"]).exists():
        return HTMLResponse("Not found", 404)
    return FileResponse(reel["video_path"], media_type="video/mp4")


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
        c["allowance"] = max(jobs.clip_allowance(c["id"]), 0)
    return page("clips.html", request, clips=clips)


STAGES = [("analysing", "Uploaded · analysing"), ("making", "Researching · making reels"), ("review", "Waiting for you"),
          ("scheduled", "Scheduled"), ("posted", "Posted · tracking 24/48/72h"), ("done", "Results in")]


def pipeline():
    """Every clip and reel, put in the column for the stage it's at."""
    cols = {k: [] for k, _ in STAGES}
    for c in db.q("SELECT * FROM clips WHERE kind = 'main' AND status IN ('new', 'analysing', 'analysed', 'making', 'failed') ORDER BY created_at DESC"):
        stage = "making" if c["status"] == "making" or (c["status"] == "failed" and c["subject"]) else "analysing"
        if c["status"] == "analysed":  # analysed, not made yet: in review mode reels are on the way; autopilot uses it later
            stage = "making" if jobs.setting("mode") == "review" else "analysing"
        cols[stage].append({"type": "clip", **c})
    done = {s["reel_id"] for s in db.q("SELECT reel_id FROM snapshots WHERE hours = 72")}
    snaps = {s["reel_id"]: s for s in db.q("SELECT * FROM snapshots ORDER BY hours")}
    for r in db.q("""SELECT r.*, c.filename FROM reels r JOIN clips c ON c.id = r.clip_id
                     WHERE r.status != 'rejected' ORDER BY COALESCE(r.post_at, r.created_at) DESC LIMIT 200"""):
        stage = {"rendering": "making", "draft": "review", "failed": "review", "scheduled": "scheduled",
                 "posting": "scheduled", "posted": "done" if r["id"] in done else "posted"}[r["status"]]
        cols[stage].append({"type": "reel", "snap": snaps.get(r["id"]), **r})
    brolls = db.q("SELECT * FROM clips WHERE kind = 'broll' ORDER BY created_at DESC")
    return [(k, label, cols[k]) for k, label in STAGES], brolls


async def upload_page(request: Request):
    stages, brolls = pipeline()
    picked = request.query_params.get("clips", "")
    library = [c for c in (db.one("SELECT id, filename, kind, subject, description, duration FROM clips WHERE id = ?", i)
                           for i in picked.split(",") if i) if c]
    return page("upload.html", request, stages=stages, brolls=brolls, picked=library, mix=jobs.research_mix())


async def upload_start(request: Request):
    """The Start button: a batch of new files (sent next) and/or clips picked from the library."""
    data = await request.json()
    library = [x for x in data.get("library", []) if db.one("SELECT id FROM clips WHERE id = ?", x.get("id"))]
    for x in library:
        if x.get("note"):
            db.update("clips", x["id"], description=x["note"])
        if x.get("kind") in ("main", "broll"):
            db.update("clips", x["id"], kind=x["kind"])
    jobs.start_batch(data["batch"], data.get("combine"), int(data.get("expected") or 0), [x["id"] for x in library],
                     data.get("mix"))
    return JSONResponse({"ok": True})


async def pipeline_part(request: Request):
    stages, brolls = pipeline()
    html = templates.get_template("_pipeline.html").render(stages=stages, brolls=brolls, busy=jobs.busy())
    return HTMLResponse(html)


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
        note = " ".join(x for x in (form.get("description"), form.get("note")) if x and x.strip())
        jobs.add_clip(dest, f.filename, None if kind == "auto" else kind, note,
                      keep_look=form.get("keep_look") == "1", batch=form.get("batch") or None)
        count += 1
    for f in form.getlist("music"):
        if getattr(f, "filename", None) and Path(f.filename).suffix.lower() in editor.AUDIO_EXTS:
            with (db.AUDIO_DIR / Path(f.filename).name).open("wb") as out:
                shutil.copyfileobj(f.file, out, 1 << 20)
    db.log(f"Uploaded {count} clip(s)")
    if request.headers.get("x-requested-with") == "fetch":
        return JSONResponse({"ok": True, "clips": count})
    return RedirectResponse(request.headers.get("referer", "/upload"), 303)


async def clip_action(request: Request):
    clip_id, action = request.path_params["id"], request.path_params["action"]
    form = await request.form()
    if action == "kind":
        db.update("clips", clip_id, kind=form["kind"])
    elif action == "silent":
        db.update("clips", clip_id, broll_silent=1 if form.get("silent") == "1" else 0)
    elif action == "describe":
        db.update("clips", clip_id, description=(form.get("description") or "").strip() or None)
        if form.get("reanalyse"):
            failed = db.one("SELECT status FROM clips WHERE id = ?", clip_id)["status"] == "failed"
            jobs.submit("re-analyse", jobs.analyse_clip, clip_id, False, failed)  # a retry carries on to making reels
    elif action == "make":
        jobs.submit("make reels", jobs.make_reels, clip_id, int(form.get("n") or 3))
    elif action == "delete":
        clip = db.one("SELECT * FROM clips WHERE id = ?", clip_id)
        Path(clip["path"]).unlink(missing_ok=True)
        db.run("DELETE FROM clips WHERE id = ?", clip_id)
    return RedirectResponse("/clips", 303)


# --------------------------------------------------------------------------- schedule + results

async def calendar(request: Request):
    """Month view: a small picture per reel on its day. Tap one for all its details."""
    today = jobs.local_now().date()
    month = request.query_params.get("m") or f"{today:%Y-%m}"
    first = datetime.strptime(month + "-01", "%Y-%m-%d").date()
    nxt = (first.replace(day=28) + timedelta(days=4)).replace(day=1)
    prev = (first - timedelta(days=1)).replace(day=1)
    grid_start = first - timedelta(days=first.weekday())
    grid_end = nxt + timedelta(days=(7 - nxt.weekday()) % 7)
    rows = db.q("""SELECT r.*, c.filename FROM reels r JOIN clips c ON c.id = r.clip_id
                   WHERE r.status IN ('scheduled', 'posting', 'posted', 'failed', 'draft')""")
    days = {grid_start + timedelta(days=i): [] for i in range((grid_end - grid_start).days)}
    for r in rows:
        when = r["posted_at"] if r["status"] == "posted" else r["post_at"] or (r["recommended_time"] if r["status"] == "draft" else None)
        if not when:
            continue
        d = datetime.fromisoformat(when).date()
        if d in days:
            days[d].append({**r, "when": when})
    for items in days.values():
        items.sort(key=lambda r: r["when"])
    in_month = [r for d, items in days.items() if first <= d < nxt for r in items]
    counts = Counter(r["status"] for r in in_month)
    weeks = [list(days.items())[i:i + 7] for i in range(0, len(days), 7)]
    return page("calendar.html", request, weeks=weeks, first=first, today=today, counts=counts,
                prev=f"{prev:%Y-%m}", next=f"{nxt:%Y-%m}", this=f"{today:%Y-%m}", month=month, times=jobs.posting_times())


async def reel_page(request: Request):
    """Everything about one reel: the video, hook, caption, score, reasons, research, and when it goes out."""
    r = db.one("""SELECT r.*, c.filename, c.duration AS clip_seconds FROM reels r JOIN clips c ON c.id = r.clip_id
                  WHERE r.id = ?""", request.path_params["id"])
    if not r:
        return RedirectResponse("/calendar", 303)
    r["look_note"] = look_note(r["grade"], db.latest_research("look"))
    snaps = db.q("SELECT * FROM snapshots WHERE reel_id = ? ORDER BY hours", r["id"])
    brolls = db.q("SELECT * FROM clips WHERE kind = 'broll' ORDER BY created_at DESC")
    r["remake"] = db.one("SELECT id, on_screen_text, status FROM reels WHERE parent = ? AND status != 'rejected'", r["id"])
    return page("reel.html", request, r=r, snaps=snaps, brolls=brolls, times=jobs.next_free_slots(6),
                hashtags=jobs.cfg()["posting"].get("hashtags", ""))


async def results(request: Request):
    reels = db.q("SELECT * FROM reels WHERE status = 'posted' ORDER BY posted_at DESC")
    usual = jobs.usual_views()
    snaps = {}
    for s in db.q("SELECT * FROM snapshots"):
        snaps.setdefault(s["reel_id"], {})[s["hours"]] = s
    for r in reels:
        r["snaps"] = snaps.get(r["id"], {})
        latest = r["snaps"].get(72) or r["snaps"].get(48) or r["snaps"].get(24)
        r["latest"] = latest
        r["remake"] = db.one("SELECT id, on_screen_text, status FROM reels WHERE parent = ? AND status != 'rejected'", r["id"])
        final = r["snaps"].get(72) or r["snaps"].get(48)
        r["actual"] = jobs.actual_score(final["views"], usual) if final else None
        r["actual_final"] = bool(r["snaps"].get(72))
    scored = [r for r in reels if r["snaps"].get(72) or r["snaps"].get(48)]
    summary = None
    if scored:
        views = [(r["snaps"].get(72) or r["snaps"].get(48))["views"] or 0 for r in scored]
        summary = {"reels": len(scored), "median": int(statistics.median(views)), "best": max(views)}

    return page("results.html", request, reels=reels, summary=summary, by_source=jobs.source_results(days=3650),
                recent=jobs.source_results(), mix=jobs.research_mix(), mix_change=db.latest_research("mix_change"),
                auto=jobs.setting("mix_auto"))


# --------------------------------------------------------------------------- research + settings

async def research(request: Request):
    if request.method == "POST":
        form = await request.form()
        if form.get("run") == "radar":
            jobs.submit("competitor radar", jobs.run_radar)
        elif form.get("run") == "history":
            jobs.submit("refresh history", jobs.refresh_history)
        elif form.get("run") == "trends":
            jobs.submit("google trends", jobs.google_trends, 0)
        elif form.get("run") == "save":
            jobs.save_links(form.get("links") or "", (form.get("note") or "").strip())
            return RedirectResponse("/research#library", 303)
        elif form.get("run") == "forget":
            db.run("DELETE FROM library WHERE id = ?", form.get("id"))
            return RedirectResponse("/research#library", 303)
        return RedirectResponse("/research", 303)
    q, src = request.query_params.get("q", "").strip(), request.query_params.get("source", "")
    sql, args = "SELECT * FROM library WHERE account = ?", [db.ACCOUNT]
    if q:
        sql += " AND (on_screen_text LIKE ? OR post_caption LIKE ? OR creator LIKE ? OR tags LIKE ? OR note LIKE ? OR music LIKE ?)"
        args += [f"%{q}%"] * 6
    if src:
        sql += " AND source = ?"
        args.append(src)
    library = db.q(sql + " ORDER BY (source = 'saved') DESC, views DESC LIMIT 150", *args)
    month = f"{jobs.local_now():%Y-%m}"
    usage = {"scrapes": db.get_setting(f"apify_runs:{month}", 0), "reused": db.get_setting(f"library_reuse:{month}", 0),
             "total": db.one("SELECT COUNT(*) n FROM library WHERE account = ?", db.ACCOUNT)["n"]}
    return page("research.html", request, best=db.latest_research("best_times"), topic=db.latest_research("topic"),
                radar=db.latest_research("radar"), times=jobs.posting_times(), trends=db.latest_research("trends"),
                tiktok=db.latest_research("tiktok"), library=library, usage=usage, q=q, src=src,
                spend=jobs.apify_spend(fresh=request.query_params.get("refresh") == "1"),
                budget=float(jobs.setting("research_budget") or 0), board=jobs.whats_worked(),
                radar_source=jobs.cfg()["radar"].get("source", "meta"),
                look=db.latest_research("look"))


async def connect_instagram(request: Request):
    if not connect.ready():
        return RedirectResponse("/settings?connect=setup#instagram", 303)
    return RedirectResponse(connect.login_url(), 303)


async def connect_done(request: Request):
    q = request.query_params
    if q.get("error"):
        db.log(f"Instagram connect cancelled: {q.get('error_description') or q['error']}")
        return RedirectResponse("/settings#instagram", 303)
    try:
        connect.finish(q.get("code"), q.get("state"))
    except Exception as e:
        db.log(f"✗ Instagram connect failed: {e}")
    return RedirectResponse("/settings#instagram", 303)


async def disconnect_instagram(request: Request):
    connect.disconnect()
    return RedirectResponse("/settings#instagram", 303)


async def settings_page(request: Request):
    if request.method == "POST":
        form = await request.form()
        for key in ("mode", "niche", "times_mode", "text_style", "grade", "hashtags", "radar_source", "apify_mode"):
            if key in form:
                db.set_setting(key, form[key])
        for key in ("posts_per_day", "reels_per_clip", "reel_seconds", "research_refresh_days"):
            if form.get(key):
                db.set_setting(key, int(form[key]))
        if all(form.get(f"mix_{s}") not in (None, "") for s in jobs.SOURCES):
            mix = {s: max(int(form[f"mix_{s}"]), 0) for s in jobs.SOURCES}
            total = sum(mix.values()) or 1
            scaled = jobs.mix_counts(100, mix) if total != 100 else mix  # always save a mix that adds up to 100%
            for s in jobs.SOURCES:
                db.set_setting(f"mix_{s}", scaled[s])
            db.set_setting("mix_auto", form.get("mix_auto") == "1")
        if form.get("research_budget") not in (None, ""):
            db.set_setting("research_budget", max(0.0, float(form["research_budget"])))
        db.set_setting("broll_silent", form.get("broll_silent") == "1")
        if form.get("post_times") is not None:
            db.set_setting("post_times", [t.strip() for t in form["post_times"].split(",") if t.strip()])
        if form.get("competitors") is not None:
            names = [n.strip().lstrip("@") for n in form["competitors"].replace(",", "\n").splitlines() if n.strip()]
            db.set_setting("competitors", [{"username": n, "notes": ""} for n in names])
        db.log("Settings saved")
        return RedirectResponse("/settings", 303)
    c = jobs.cfg()
    keys = {"ANTHROPIC_API_KEY": bool(claude_key())} | {k: bool(env(k, required=False)) for k in ("IG_ACCESS_TOKEN", "IG_USER_ID", "APIFY_TOKEN", "APP_PASSWORD")}
    return page("settings.html", request, c=c, mix=jobs.research_mix(), mix_change=db.latest_research("mix_change"),
                outlook=jobs.outlook(), labels=jobs.SOURCE_LABELS,
                sources=jobs.SOURCES, s={k: jobs.setting(k) for k in jobs.EDITABLE}, keys=keys,
                styles=list(editor.TEXT_STYLES), grades=list(editor.GRADES), ig=connect.status(), meta_ready=connect.ready(),
                redirect_uri=connect.redirect_uri(), setup=request.query_params.get("connect") == "setup")


async def home(request: Request):
    """The signed-in home page: "Let's get creative", with a chat box to make reels or ask a question."""
    reels = db.q("SELECT * FROM reels WHERE status != 'rejected' ORDER BY created_at DESC")
    latest = {snap["reel_id"]: snap for snap in db.q("SELECT * FROM snapshots ORDER BY hours")}
    views = [latest[r["id"]]["views"] or 0 for r in reels if r["id"] in latest]
    stats = {"made": len(reels), "posted": sum(1 for r in reels if r["status"] == "posted"),
             "typical": int(statistics.median(views)) if views else 0,
             "learned": sum(1 for r in reels if r["lesson"])}
    journey = next((j for j in remake_journeys(reels, latest, 10) if j["lift"]), None)
    trend = db.latest_research("trends")
    return page("home.html", request, stats=stats, journey=journey,
                trending=[t["term"] for t in (trend or {}).get("items", [])[:6]])


TINTS = {"instagram": ["#4A1752", "#9C3D84"], "tiktok": ["#16295E", "#3A62B8"],  # dark → light; white text passes AA
         "trends": ["#6E2316", "#A84C2A"], "original": ["#3A2A08", "#7E5814"]}


def _ago(iso):
    try:
        then = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return ""
    secs = (datetime.now(timezone.utc) - (then if then.tzinfo else then.replace(tzinfo=timezone.utc))).total_seconds()
    for unit, size in (("d", 86400), ("h", 3600), ("m", 60)):
        if secs >= size:
            return f"{int(secs // size)}{unit} ago"
    return "just now"


async def overview(request: Request):
    """The dashboard: this week's reels, your numbers, your best reels and the latest ones."""
    now = jobs.local_now()
    latest = {}
    for snap in db.q("SELECT * FROM snapshots ORDER BY hours"):
        latest[snap["reel_id"]] = snap
    reels = db.q("SELECT r.*, c.duration AS clip_seconds FROM reels r LEFT JOIN clips c ON c.id = r.clip_id "
                 "WHERE r.status != 'rejected' ORDER BY r.created_at DESC")
    local_day = lambda iso: (datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(jobs.tz()).date() if iso else None)
    week = []
    for back in range(6, -1, -1):
        day = (now - timedelta(days=back)).date()
        week.append({"day": day.strftime("%a"), "v": sum(1 for r in reels if local_day(r["created_at"]) == day)})
    posted = [r for r in reels if r["status"] == "posted"]
    posted_days = {(r["posted_at"] or "")[:10] for r in posted}
    streak, day = 0, now.date()
    if str(day) not in posted_days:
        day -= timedelta(days=1)
    while str(day) in posted_days:
        streak += 1
        day -= timedelta(days=1)
    views_week = sum((latest.get(r["id"]) or {}).get("views") or 0 for r in posted
                     if r["posted_at"] and r["posted_at"][:10] >= str((now - timedelta(days=7)).date()))
    with_views = [(latest[r["id"]]["views"] or 0) for r in posted if r["id"] in latest]
    spend, budget = jobs.apify_spend(), float(jobs.setting("research_budget") or 0)

    def feature(r):
        snap = latest.get(r["id"]) or {}
        lesson = json.loads(r["lesson"]) if r["lesson"] else None
        src = r["source"] or ("trends" if r["risky"] else "instagram")
        if snap:
            stats = [("Views", f"{snap.get('views') or 0:,}"), ("Shares", f"{snap.get('shares') or 0:,}"), ("Saves", f"{snap.get('saved') or 0:,}")]
        else:
            stats = [("Score", f"{r['virality_score'] or 0}/100"), ("Source", jobs.SOURCE_LABELS[src].split(" ", 1)[1]),
                     ("Status", {"draft": "Review", "scheduled": "Scheduled", "rendering": "Making"}.get(r["status"], r["status"].title()))]
        return {"id": r["id"], "title": r["on_screen_text"], "kicker": "Top reel" if snap else "Up next", "stats": stats,
                "desc": (lesson or {}).get("headline") or r["score_reason"] or r["angle"] or "",
                "tint": TINTS.get(src, TINTS["trends"]), "share": r["permalink"] or f"/reel/{r['id']}", "fav": bool(r["favourite"])}
    top = sorted((r for r in posted if r["id"] in latest), key=lambda r: (-(r["favourite"] or 0), -(latest[r["id"]]["views"] or 0)))[:5]
    if len(top) < 3:
        top += sorted((r for r in reels if r["status"] in ("draft", "scheduled")), key=lambda r: -(r["virality_score"] or 0))[:3 - len(top)]
    q = request.query_params.get("q", "").strip()
    recent = [r for r in reels if r["status"] != "rendering" and (not q or q.lower() in f"{r['on_screen_text']} {r['post_caption']}".lower())][:4 if not q else 12]
    status_word = {"draft": "Waiting for review", "scheduled": "Scheduled", "posted": "Posted", "failed": "Failed"}
    conn = connect.status()
    journeys = remake_journeys(reels, latest)
    return page("overview.html", request, week=week, total=sum(d["v"] for d in week), views_week=views_week, streak=streak,
                month=sum(1 for r in reels if (r["created_at"] or "")[:7] == f"{now:%Y-%m}"),
                profile={"name": conn.get("username") or "Your account", "handle": conn.get("username"),
                         "made": len(reels), "posted": len(posted),
                         "median": int(statistics.median(with_views)) if with_views else 0},
                spend=spend, budget=budget, featured=[feature(r) for r in top], q=q,
                recent=[{"id": r["id"], "title": r["on_screen_text"], "when": f"{status_word.get(r['status'], r['status'])} · {_ago(r['created_at'])}"}
                        for r in recent], alerts=db.q("SELECT * FROM events ORDER BY id DESC LIMIT 8"), journeys=journeys)


def _day(iso):
    try:
        d = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except (AttributeError, ValueError):
        return ""
    if d.tzinfo:
        d = d.astimezone(jobs.tz())
    return f"{d:%a} {d.day} {d:%b}"


def remake_journeys(reels, latest, limit=4):
    """Each reel Creatr learned from and remade: made → live → learned → remade → live → result, with views per check."""
    by_id = {r["id"]: r for r in reels}
    snaps = {}
    for snap in db.q("SELECT reel_id, hours, views FROM snapshots ORDER BY hours"):
        snaps.setdefault(snap["reel_id"], []).append([snap["hours"], snap["views"] or 0])
    out = []
    for remake in reels:
        first = by_id.get(remake["parent"])
        if not first:
            continue
        lesson = json.loads(first["lesson"]) if first["lesson"] else {}
        v1 = (latest.get(first["id"]) or {}).get("views")
        v2 = (latest.get(remake["id"]) or {}).get("views")
        steps = [{"label": "Made", "when": _day(first["created_at"]), "text": f"“{first['on_screen_text']}”", "kind": "made"}]
        if first["posted_at"]:
            steps.append({"label": "Went live", "when": _day(first["posted_at"]), "kind": "live",
                          "text": f"{v1:,} views" if v1 is not None else "waiting for results"})
        if lesson:
            steps.append({"label": "Creatr learned", "when": _day(lesson.get("reviewed_at")), "kind": f"learn-{lesson.get('verdict', 'ok')}",
                          "text": lesson.get("headline", "")})
        steps.append({"label": "Remade", "when": _day(remake["created_at"]), "kind": "remade",
                      "text": f"“{remake['on_screen_text']}” · {lesson.get('tweak', '')}".strip(" ·")})
        if remake["posted_at"]:
            steps.append({"label": "Went live", "when": _day(remake["posted_at"]), "kind": "live",
                          "text": f"{v2:,} views" if v2 is not None else "waiting for results"})
        lift = round(v2 / v1, 1) if v1 and v2 is not None else None
        out.append({"first": first["id"], "remake": remake["id"], "title": first["on_screen_text"], "steps": steps,
                    "v1": v1, "v2": v2, "lift": lift, "s1": snaps.get(first["id"], []), "s2": snaps.get(remake["id"], []),
                    "status": remake["status"]})
    out.sort(key=lambda j: -(j["lift"] or 0))
    return out[:limit]


async def favourite(request: Request):
    reel = db.one("SELECT favourite FROM reels WHERE id = ?", request.path_params["id"])
    if not reel:
        return JSONResponse({"error": "not found"}, 404)
    db.update("reels", request.path_params["id"], favourite=0 if reel["favourite"] else 1)
    return JSONResponse({"favourite": not reel["favourite"]})


async def logout(request: Request):
    resp = RedirectResponse("/login", 303)
    resp.delete_cookie("rb")
    return resp


async def ask(request: Request):
    """The home page chat box, when no clips are attached: Creatr answers from your research and results."""
    question = ((await request.json()).get("question") or "").strip()[:2000]
    if not question:
        return JSONResponse({"error": "Type a question first."}, 400)
    try:
        context, _ = jobs.build_context(db.latest_research("topic"), db.latest_research("tiktok"))
        answer = await asyncio.to_thread(brain.ask, question, context, jobs.cfg()["niche"])
    except Exception as e:
        return JSONResponse({"error": f"Couldn't answer that: {str(e)[:200]}"}, 500)
    return JSONResponse({"answer": answer})


async def resume_posting(request: Request):
    db.set_setting("posting_paused", None)
    db.log("Posting resumed")
    return RedirectResponse(request.headers.get("referer", "/"), 303)


async def health(request: Request):
    return JSONResponse({"ok": True, "queue": jobs.busy()})


routes = [
    Route("/", home), Route("/health", health), Route("/ask", ask, methods=["POST"]), Route("/overview", overview),
    Route("/logout", logout), Route("/reels/{id}/favourite", favourite, methods=["POST"]),
    Route("/login", login, methods=["GET", "POST"]),
    Route("/review", review),
    Route("/reels/remake-all", rerender_all, methods=["POST"]),
    Route("/posting/resume", resume_posting, methods=["POST"]),
    Route("/reels/{id}/{action}", reel_action, methods=["POST"]),
    Route("/video/{id}.mp4", video), Route("/public/{id}.mp4", public_video), Route("/thumb/{id}.jpg", thumb), Route("/spots/{id}.jpg", thumb_spots), Route("/clipthumb/{id}.jpg", clip_thumb),
    Route("/clips", clips_page), Route("/upload", upload_page), Route("/upload", upload, methods=["POST"]),
    Route("/pipeline", pipeline_part), Route("/reel/{id}", reel_page), Route("/upload/start", upload_start, methods=["POST"]), Route("/calendar", calendar),
    Route("/clips/{id}/{action}", clip_action, methods=["POST"]),
    Route("/schedule", lambda r: RedirectResponse("/calendar", 303)), Route("/results", results),
    Route("/research", research, methods=["GET", "POST"]),
    Route("/settings", settings_page, methods=["GET", "POST"]),
    Route("/connect/instagram", connect_instagram), Route("/connect/instagram/done", connect_done),
    Route("/connect/instagram/disconnect", disconnect_instagram, methods=["POST"]),
    Mount("/static", StaticFiles(directory=HERE / "static"), name="static"),
]

@contextlib.asynccontextmanager
async def lifespan(app):
    connect.apply()
    jobs.start()
    yield


app = Starlette(routes=routes, middleware=[Middleware(Auth)], lifespan=lifespan)
