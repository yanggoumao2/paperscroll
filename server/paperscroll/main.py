"""HTTP API + static web UI."""
from __future__ import annotations

import asyncio
import csv
import io
import json
import logging
import re
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import config, db, figures, jobs, rank
from .embed import INDEX

log = logging.getLogger("paperscroll")


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init()
    jobs.start()
    yield
    jobs.stop()


app = FastAPI(title="PaperScroll", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


# ------------------------------------------------------------------ status / config

def web_version() -> str:
    """Changes whenever any UI file changes; the app compares it to offer a reload."""
    m = max((p.stat().st_mtime for p in config.WEB.rglob("*") if p.is_file() and "download" not in p.parts), default=0)
    return str(int(m))


@app.middleware("http")
async def no_stale_ui(request, call_next):
    resp = await call_next(request)
    path = request.url.path
    if not path.startswith("/api/") and not path.startswith("/download/") and not path.startswith("/fonts/") and not path.startswith("/vendor/"):
        resp.headers["Cache-Control"] = "no-cache"
    return resp


@app.get("/api/status")
def status():
    con = db.connect()
    total = con.execute("SELECT COUNT(*) c FROM papers").fetchone()["c"]
    newest = con.execute("SELECT MAX(published) m FROM papers").fetchone()["m"]
    enriched = con.execute("SELECT COUNT(*) c FROM papers WHERE s2_at IS NOT NULL").fetchone()["c"]
    oa = con.execute("SELECT COUNT(*) c FROM papers WHERE oa_at IS NOT NULL").fetchone()["c"]
    con.close()
    cfg = config.load()
    return {"papers": total, "indexed": len(INDEX.ids), "s2_enriched": enriched, "newest": newest,
            "job": jobs.STATUS, "categories": cfg["categories"], "window_days": cfg["window_days"],
            "sync_times": cfg["sync_times"], "has_s2_key": bool(cfg.get("s2_api_key")),
            "has_openalex_key": bool(cfg.get("openalex_api_key")), "oa_enriched": oa, "web_version": web_version()}


class ConfigIn(BaseModel):
    categories: list[str] | None = None
    window_days: int | None = None
    s2_api_key: str | None = None
    openalex_api_key: str | None = None


CAT_RE = re.compile(r"^[a-z\-]+(\.[A-Za-z\-]+)?$")


@app.put("/api/config")
def put_config(c: ConfigIn):
    cfg = config.load()
    if c.categories is not None:
        cats = [x.strip() for x in c.categories if x.strip()]
        bad = [x for x in cats if not CAT_RE.match(x)]
        if bad or not cats:
            raise HTTPException(400, f"invalid categories: {bad}")
        cfg["categories"] = list(dict.fromkeys(cats))
    if c.window_days is not None:
        cfg["window_days"] = max(7, min(730, c.window_days))
    if c.s2_api_key is not None:
        cfg["s2_api_key"] = c.s2_api_key.strip()
    if c.openalex_api_key is not None:
        cfg["openalex_api_key"] = c.openalex_api_key.strip()
    config.save(cfg)
    jobs.trigger()
    return status()


@app.post("/api/sync")
def sync():
    return {"started": jobs.trigger()}


# ------------------------------------------------------------------ profile + feed

class ProfileIn(BaseModel):
    topic: str = ""
    keywords: str = ""
    prefs: dict = {}


@app.get("/api/profile")
def get_profile():
    return rank.get_profile()


@app.put("/api/profile")
def put_profile(p: ProfileIn):
    return rank.set_profile(p.topic, p.keywords, p.prefs)


class FeedIn(BaseModel):
    n: int = 6
    pin: str | None = None


@app.post("/api/feed")
async def feed(f: FeedIn):
    cfg = config.load()
    ids, exp, why = rank.feed(max(1, min(20, f.n)), int(cfg["window_days"]), f.pin, cfg.get("recommender", "v2"))
    task = asyncio.ensure_future(figures.ensure(ids))
    try:   # wait briefly for figures/affiliations; the rest is fetched lazily by /api/img
        await asyncio.wait_for(asyncio.shield(task), 5)
    except asyncio.TimeoutError:
        pass
    cards = rank.cards_for(ids)
    for c in cards:
        c["explore"] = c["id"] in exp
        c["why"] = why.get(c["id"], {})
    return {"cards": cards, "indexed": len(INDEX.ids), "job": jobs.STATUS}


@app.get("/api/recsys")
def recsys_state():
    """What the recommender has learned so far: interests, usual dwell time."""
    from . import recsys
    return {**recsys.explain(), "version": config.load().get("recommender", "v2")}


@app.post("/api/reset_seen")
def reset_seen():
    with db.writer() as w:
        w.execute("DELETE FROM seen")
    return {"ok": True}


@app.get("/api/paper/{pid:path}")
async def paper(pid: str):
    await figures.ensure([pid])
    cards = rank.cards_for([pid])
    if not cards:
        raise HTTPException(404, "paper not in local database")
    return cards[0]


@app.get("/api/img/{pid:path}")
async def img(pid: str):
    await figures.ensure([pid])          # no-op when the figure was already looked up
    data = await figures.image_bytes(pid)
    if not data:
        raise HTTPException(404)
    return Response(data, media_type="image/jpeg", headers={"Cache-Control": "public, max-age=604800"})


# ------------------------------------------------------------------ events / library

class EventIn(BaseModel):
    id: str
    kind: str            # view | skip | like | unlike | save | unsave | hide | unhide | comment | fig | read | link | share
    dwell: float | None = None
    text: str | None = None
    eid: str | None = None


FLAGS = {"like": ("liked", 1), "unlike": ("liked", 0), "save": ("saved", 1), "unsave": ("saved", 0),
         "hide": ("hidden", 1), "unhide": ("hidden", 0)}


@app.post("/api/event")
def event(e: EventIn):
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with db.writer() as w:
        cur = w.execute("INSERT OR IGNORE INTO events(ts,id,kind,dwell,text,eid) VALUES(?,?,?,?,?,?)",
                        (now, e.id, e.kind, e.dwell, e.text, (e.eid or None) and e.eid[:40]))
        if not cur.rowcount:   # duplicate of an event already stored
            return {"ok": True, "dup": True}
        if e.kind in FLAGS or e.kind == "comment":
            w.execute("INSERT OR IGNORE INTO interactions(id, updated) VALUES(?,?)", (e.id, now))
        if e.kind in FLAGS:
            col, val = FLAGS[e.kind]
            extra = {"liked": ", liked_at=?", "saved": ", saved_at=?"}.get(col, "")
            args = [val, now] + ([now] if extra else []) + [e.id]
            w.execute(f"UPDATE interactions SET {col}=?, updated=?{extra} WHERE id=?", args)
        elif e.kind == "comment":
            w.execute("UPDATE interactions SET comment=?, updated=? WHERE id=?", ((e.text or "").strip() or None, now, e.id))
    return {"ok": True}


def _library(kind: str) -> list[dict]:
    cond = {"like": "liked=1", "save": "saved=1", "note": "comment IS NOT NULL AND comment!=''",
            "hidden": "hidden=1"}.get(kind, "liked=1 OR saved=1 OR (comment IS NOT NULL AND comment!='')")
    con = db.connect()
    ids = [r["id"] for r in con.execute(f"SELECT id FROM interactions WHERE {cond} ORDER BY updated DESC")]
    con.close()
    return rank.cards_for(ids)


@app.get("/api/library")
def library(kind: str = "all"):
    return {"cards": _library(kind)}


def _bibtex(c: dict) -> str:
    year = (c["published"] or "0000")[:4]
    last = (c["first_author"].split() or ["anon"])[-1]
    first_word = re.sub(r"[^A-Za-z]", "", (c["title"].split() or ["x"])[0]).lower()
    key = re.sub(r"[^A-Za-z0-9]", "", f"{last}{year}{first_word}")
    esc = lambda s: (s or "").replace("{", "\\{").replace("}", "\\}")
    lines = [f"@misc{{{key},", f"  title = {{{esc(c['title'])}}},", f"  author = {{{' and '.join(c['authors'])}}},",
             f"  year = {{{year}}},", f"  eprint = {{{c['id']}}},", "  archivePrefix = {arXiv},",
             f"  primaryClass = {{{c['primary']}}},", f"  url = {{{c['arxiv_url']}}},"]
    if c.get("doi"):
        lines.append(f"  doi = {{{c['doi']}}},")
    if c.get("venue"):
        lines.append(f"  note = {{{esc(c['venue'])}}},")
    return "\n".join(lines) + "\n}\n"


@app.get("/api/export")
def export(kind: str = "all", fmt: str = "bibtex"):
    cards = _library(kind)
    stamp = datetime.now().strftime("%Y%m%d")
    if fmt == "json":
        body, mt, ext = json.dumps(cards, ensure_ascii=False, indent=2), "application/json", "json"
    elif fmt == "csv":
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["arxiv_id", "title", "authors", "published", "venue", "citations", "liked", "saved", "note", "url"])
        for c in cards:
            w.writerow([c["id"], c["title"], "; ".join(c["authors"]), c["published"], c["venue"], c["citations"],
                        int(c["liked"]), int(c["saved"]), c["note"], c["arxiv_url"]])
        body, mt, ext = "﻿" + buf.getvalue(), "text/csv", "csv"
    elif fmt == "md":
        parts = [f"# PaperScroll 导出 {stamp}\n"]
        for c in cards:
            flags = " ".join(x for x, y in (("❤", c["liked"]), ("★", c["saved"])) if y)
            parts.append(f"## {c['title']} {flags}\n\n- arXiv: [{c['id']}]({c['arxiv_url']}) · {c['published']}"
                         + (f" · {c['venue']}" if c["venue"] else "")
                         + f"\n- Authors: {', '.join(c['authors'][:8])}{' et al.' if c['n_authors'] > 8 else ''}\n"
                         + (f"- 笔记: {c['note']}\n" if c["note"] else "")
                         + f"\n> {c['tldr']}\n\n{c['abstract']}\n")
        body, mt, ext = "\n".join(parts), "text/markdown", "md"
    else:
        body, mt, ext = "\n".join(_bibtex(c) for c in cards), "application/x-bibtex", "bib"
    return Response(body.encode("utf-8"), media_type=f"{mt}; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="paperscroll-{kind}-{stamp}.{ext}"'})


# ------------------------------------------------------------------ web UI

@app.get("/p/{pid:path}")
def share(pid: str):
    return RedirectResponse(f"/?p={pid}")


@app.get("/")
def index():
    return FileResponse(config.WEB / "index.html", headers={"Cache-Control": "no-cache"})


app.mount("/", StaticFiles(directory=config.WEB), name="web")


@app.exception_handler(Exception)
async def err(_req, ex):
    log.exception("unhandled")
    return JSONResponse({"error": repr(ex)}, status_code=500)
