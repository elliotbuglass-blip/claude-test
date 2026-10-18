"""ReelBot's memory: a small SQLite database (one file, kept on the server's disk).

Built for one account now, but every table has an `account` column so customers can be added later.
"""

import json
import os
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

from ..settings import ROOT

STORAGE = Path(os.environ.get("REELBOT_STORAGE", ROOT / "storage"))
CLIPS_DIR = STORAGE / "clips"
RENDERS_DIR = STORAGE / "renders"
AUDIO_DIR = STORAGE / "audio"
DB_PATH = STORAGE / "reelbot.db"
ACCOUNT = "me"

SCHEMA = """
CREATE TABLE IF NOT EXISTS clips (
    id TEXT PRIMARY KEY, account TEXT, filename TEXT, path TEXT,
    kind TEXT DEFAULT 'main',            -- main | broll
    broll_silent INTEGER DEFAULT 1,
    duration REAL, subject TEXT, hashtags TEXT, notes TEXT,
    status TEXT DEFAULT 'new',           -- new | analysed | used
    created_at TEXT
);
CREATE TABLE IF NOT EXISTS reels (
    id TEXT PRIMARY KEY, account TEXT, clip_id TEXT, broll TEXT,
    on_screen_text TEXT, post_caption TEXT, angle TEXT, inspired_by TEXT,
    sound_suggestion TEXT, track TEXT, seconds REAL, start REAL,
    text_style TEXT, grade TEXT, text_position REAL,
    virality_score INTEGER, score_reason TEXT,
    recommended_time TEXT, post_at TEXT,
    status TEXT DEFAULT 'rendering',     -- rendering | draft | scheduled | posting | posted | failed | rejected
    mode TEXT, video_path TEXT, media_id TEXT, permalink TEXT, posted_at TEXT, error TEXT,
    created_at TEXT
);
CREATE TABLE IF NOT EXISTS snapshots (
    reel_id TEXT, account TEXT, hours INTEGER, views INTEGER, reach INTEGER, likes INTEGER, comments INTEGER,
    saved INTEGER, shares INTEGER, avg_watch_ms INTEGER, taken_at TEXT,
    PRIMARY KEY (reel_id, hours)
);
CREATE TABLE IF NOT EXISTS settings (account TEXT, key TEXT, value TEXT, PRIMARY KEY (account, key));
CREATE TABLE IF NOT EXISTS research (id TEXT PRIMARY KEY, account TEXT, kind TEXT, data TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS library (
    id TEXT PRIMARY KEY, account TEXT, platform TEXT, url TEXT, creator TEXT,
    views INTEGER, likes INTEGER, shares INTEGER, music TEXT, on_screen_text TEXT, post_caption TEXT,
    tags TEXT, source TEXT,              -- research | tiktok | radar | saved (a link you added)
    note TEXT, status TEXT, posted_at TEXT, first_seen TEXT, last_seen TEXT, created_at TEXT
);
CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY AUTOINCREMENT, account TEXT, message TEXT, created_at TEXT);
"""

# Columns added after the first release: added to older databases on start-up.
NEW_COLUMNS = {
    "clips": {"description": "TEXT", "keep_look": "INTEGER", "batch": "TEXT", "combine": "INTEGER"},
    "snapshots": {"account": "TEXT"},
    "reels": {"positives": "TEXT", "negatives": "TEXT", "sound_reason": "TEXT", "trend": "TEXT",
              "cut_reason": "TEXT", "text_reason": "TEXT", "research": "TEXT", "text_spots": "TEXT", "risky": "INTEGER", "source": "TEXT", "series": "TEXT",
              "adjust": "TEXT", "chat": "TEXT", "text_layout": "TEXT", "text_scale": "REAL", "motion": "TEXT"},
}

_lock = threading.Lock()


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_id():
    return uuid.uuid4().hex[:10]


def connect():
    for d in (CLIPS_DIR, RENDERS_DIR, AUDIO_DIR):
        d.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    for table, cols in NEW_COLUMNS.items():
        have = {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
        for col, kind in cols.items():
            if col not in have:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {kind}")
    conn.commit()
    return conn


_conn = None


def conn():
    global _conn
    if _conn is None:
        _conn = connect()
    return _conn


def q(sql, *args):
    with _lock:
        return [dict(r) for r in conn().execute(sql, args).fetchall()]


def one(sql, *args):
    rows = q(sql, *args)
    return rows[0] if rows else None


def run(sql, *args):
    with _lock:
        c = conn()
        c.execute(sql, args)
        c.commit()


def insert(table, row):
    row = {"account": ACCOUNT, **row}
    if table != "snapshots":
        row.setdefault("created_at", now())
    cols = ", ".join(row)
    marks = ", ".join("?" for _ in row)
    run(f"INSERT OR REPLACE INTO {table} ({cols}) VALUES ({marks})", *row.values())


def update(table, id_, **fields):
    sets = ", ".join(f"{k} = ?" for k in fields)
    run(f"UPDATE {table} SET {sets} WHERE id = ?", *fields.values(), id_)


def get_setting(key, default=None):
    row = one("SELECT value FROM settings WHERE account = ? AND key = ?", ACCOUNT, key)
    return json.loads(row["value"]) if row else default


def set_setting(key, value):
    run("INSERT OR REPLACE INTO settings (account, key, value) VALUES (?, ?, ?)", ACCOUNT, key, json.dumps(value))


def log(message):
    print(f"[reelbot] {message}", flush=True)
    run("INSERT INTO events (account, message, created_at) VALUES (?, ?, ?)", ACCOUNT, message, now())


def save_research(kind, data):
    insert("research", {"id": new_id(), "kind": kind, "data": json.dumps(data, ensure_ascii=False)})


def latest_research(kind):
    row = one("SELECT * FROM research WHERE account = ? AND kind = ? ORDER BY created_at DESC LIMIT 1", ACCOUNT, kind)
    return json.loads(row["data"]) if row else None
