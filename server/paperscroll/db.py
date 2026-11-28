"""SQLite storage: papers + FTS5 index, the user's interactions and a key/value table."""
from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager

from . import config

SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS papers(
  rid INTEGER PRIMARY KEY,
  id TEXT UNIQUE NOT NULL,
  version INTEGER,
  title TEXT, abstract TEXT, authors TEXT,
  categories TEXT, primary_cat TEXT,
  published TEXT, updated TEXT,
  comment TEXT, journal_ref TEXT, doi TEXT,
  s2_at TEXT, tldr TEXT, venue TEXT, citations INTEGER,
  fig_state INTEGER DEFAULT 0,          -- 0 unchecked, 1 has figure, 2 no html/figure, 3 fetch error
  fig_url TEXT, affiliations TEXT,
  emb BLOB,
  added TEXT
);
CREATE INDEX IF NOT EXISTS papers_pub ON papers(published);
CREATE INDEX IF NOT EXISTS papers_s2 ON papers(s2_at);
CREATE VIRTUAL TABLE IF NOT EXISTS fts USING fts5(
  title, abstract, content='papers', content_rowid='rid', tokenize='porter unicode61');
CREATE TRIGGER IF NOT EXISTS papers_ai AFTER INSERT ON papers BEGIN
  INSERT INTO fts(rowid, title, abstract) VALUES (new.rid, new.title, new.abstract);
END;
CREATE TRIGGER IF NOT EXISTS papers_ad AFTER DELETE ON papers BEGIN
  INSERT INTO fts(fts, rowid, title, abstract) VALUES ('delete', old.rid, old.title, old.abstract);
END;
CREATE TRIGGER IF NOT EXISTS papers_au AFTER UPDATE OF title, abstract ON papers BEGIN
  INSERT INTO fts(fts, rowid, title, abstract) VALUES ('delete', old.rid, old.title, old.abstract);
  INSERT INTO fts(rowid, title, abstract) VALUES (new.rid, new.title, new.abstract);
END;
CREATE TABLE IF NOT EXISTS interactions(
  id TEXT PRIMARY KEY,
  liked INTEGER DEFAULT 0, saved INTEGER DEFAULT 0, hidden INTEGER DEFAULT 0,
  comment TEXT, liked_at TEXT, saved_at TEXT, updated TEXT
);
CREATE TABLE IF NOT EXISTS seen(id TEXT PRIMARY KEY, ts TEXT);
CREATE TABLE IF NOT EXISTS events(ts TEXT, id TEXT, kind TEXT, dwell REAL, text TEXT);
CREATE TABLE IF NOT EXISTS kv(k TEXT PRIMARY KEY, v TEXT);
CREATE TABLE IF NOT EXISTS translations(h TEXT PRIMARY KEY, lang TEXT, text TEXT, ts REAL);
"""

_write_lock = threading.RLock()


def connect() -> sqlite3.Connection:
    config.DATA.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(config.DB_PATH, timeout=30, check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA busy_timeout=30000")
    return con


def init() -> None:
    con = connect()
    con.executescript(SCHEMA)
    cols = {r["name"] for r in con.execute("PRAGMA table_info(papers)")}
    for col, typ in (("oa_at", "TEXT"), ("oa_venue", "TEXT")):   # added after the first release
        if col not in cols:
            con.execute(f"ALTER TABLE papers ADD COLUMN {col} {typ}")
    con.execute("CREATE INDEX IF NOT EXISTS papers_oa ON papers(oa_at)")   # status counts without scanning blobs
    ecols = {r["name"] for r in con.execute("PRAGMA table_info(events)")}
    if "eid" not in ecols:   # client event id: a resent event is stored once
        con.execute("ALTER TABLE events ADD COLUMN eid TEXT")
    con.execute("CREATE UNIQUE INDEX IF NOT EXISTS events_eid ON events(eid) WHERE eid IS NOT NULL")
    con.commit()
    con.close()


@contextmanager
def writer():
    """Serialise writes across threads; commits on success."""
    with _write_lock:
        con = connect()
        try:
            yield con
            con.commit()
        finally:
            con.close()


def kv_get(key: str, default=None):
    con = connect()
    try:
        row = con.execute("SELECT v FROM kv WHERE k=?", (key,)).fetchone()
        return row["v"] if row else default
    finally:
        con.close()


def kv_set(key: str, value) -> None:
    with writer() as con:
        con.execute("INSERT INTO kv(k,v) VALUES(?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v", (key, value))
