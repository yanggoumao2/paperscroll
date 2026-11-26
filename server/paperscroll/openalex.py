"""OpenAlex enrichment: citation counts and the published venue for arXiv papers (no Semantic Scholar key needed).

OpenAlex bills every request against a daily budget: without a key all users behind the same public IP
share a small free budget, with a free personal key there is far more. We therefore look papers up in
batches of 50 DOIs, cap our own daily request count, stop as soon as the server says the budget is
low, and pick up where we left off on the next run."""
from __future__ import annotations

import logging
import re
import time
from datetime import date, datetime, timedelta, timezone

import httpx

from . import config, db

log = logging.getLogger("paperscroll.openalex")

URL = "https://api.openalex.org/works"
BATCH = 50
DAILY_CAP_NOKEY = 400      # requests/day we allow ourselves on the shared free budget (≈ 20k papers)
DAILY_CAP_KEY = 8000       # requests/day with a personal key
SERIES = ("lecture notes", "communications in computer and information science", "advances in intelligent systems",
          "smart innovation", "springer proceedings", "ceur workshop")
ARXIV_ID = re.compile(r"(?:arxiv\.org/(?:abs|pdf)/|10\.48550/arxiv\.)(\d{4}\.\d{4,5})", re.I)
REPO_NAMES = {"arxiv", "arxiv (cornell university)", "corr", "ssrn", "zenodo", "biorxiv", "medrxiv", "research square"}


def _venue(item: dict) -> str:
    """First non-repository location that is a conference or journal."""
    locs = [item.get("primary_location") or {}] + (item.get("locations") or [])
    for loc in locs:
        src = loc.get("source") or {}
        name = (src.get("display_name") or "").strip()
        if not name or name.lower() in REPO_NAMES or src.get("type") == "repository" or name.lower().startswith(SERIES):
            continue
        if src.get("type") in ("conference", "journal", "book series", None):
            return name
    return ""


def _budget() -> tuple[str, int]:
    today = date.today().isoformat()
    if db.kv_get("oa_day") != today:
        db.kv_set("oa_day", today)
        db.kv_set("oa_count", "0")
    return today, int(db.kv_get("oa_count") or 0)


def enrich_pending(stop_event, status) -> int:
    cfg = config.load()
    key = (cfg.get("openalex_api_key") or "").strip()
    cap = DAILY_CAP_KEY if key else DAILY_CAP_NOKEY
    stale = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat(timespec="seconds")
    con = db.connect()
    ids = [r["id"] for r in con.execute(
        # liked/saved first, then never-looked-up papers oldest first (they are the ones that already have
        # citations or a published version), then stale ones; papers younger than 3 days wait
        "SELECT p.id FROM papers p LEFT JOIN interactions i ON i.id = p.id "
        "WHERE (p.oa_at IS NULL OR p.oa_at < ?) AND p.published < ? "
        "ORDER BY (COALESCE(i.liked, 0) + COALESCE(i.saved, 0)) DESC, (p.oa_at IS NOT NULL), p.oa_at, p.published ASC",
        (stale, (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()))]
    con.close()
    _, used = _budget()
    done = 0
    with httpx.Client(follow_redirects=True, timeout=40) as client:
        for i in range(0, len(ids), BATCH):
            if stop_event.is_set():
                break
            if used >= cap:
                status["openalex"] = f"今日额度已用完，{done} 篇已补；明天继续（剩 {len(ids) - i} 篇）"
                return done
            chunk = ids[i:i + BATCH]
            params = {"filter": "doi:" + "|".join(f"10.48550/arxiv.{p}" for p in chunk),
                      "select": "doi,cited_by_count,primary_location,locations", "per-page": BATCH}
            if key:
                params["api_key"] = key
            try:
                r = client.get(URL, params=params)
            except Exception as ex:
                log.info("OpenAlex error %r", ex)
                status["openalex"] = f"网络错误，{done} 篇已补；下次同步继续"
                return done
            used += 1
            db.kv_set("oa_count", str(used))
            if r.status_code == 429:
                status["openalex"] = f"OpenAlex 今日共享额度已用完，{done} 篇已补；明天继续"
                return done
            if r.status_code != 200:
                log.warning("OpenAlex HTTP %s: %s", r.status_code, r.text[:200])
                status["openalex"] = f"HTTP {r.status_code}，{done} 篇已补"
                return done
            found = {}
            for item in r.json().get("results", []):
                # merged works carry the publisher DOI; find the arXiv id among the locations instead
                pid = None
                for loc in [{"doi": item.get("doi")}] + (item.get("locations") or []):
                    m = ARXIV_ID.search(f"{loc.get('doi') or ''} {loc.get('landing_page_url') or ''} {loc.get('pdf_url') or ''}")
                    if m:
                        pid = m.group(1)
                        break
                if pid:
                    found[pid] = (item.get("cited_by_count"), _venue(item))
            now = datetime.now(timezone.utc).isoformat(timespec="seconds")
            rows = [(now, found.get(p, (None, ""))[0], found.get(p, (None, ""))[1] or None, p) for p in chunk]
            with db.writer() as w:
                w.executemany("UPDATE papers SET oa_at=?, citations=MAX(COALESCE(?, 0), COALESCE(citations, 0)), "
                              "oa_venue=COALESCE(?, oa_venue) WHERE id=?", rows)
            done += len(chunk)
            status["openalex"] = f"{done}/{len(ids)}"
            try:
                if int(r.headers.get("X-RateLimit-Remaining", "999")) < 50:
                    status["openalex"] = f"共享额度快用完，先停；{done} 篇已补，明天继续"
                    return done
            except ValueError:
                pass
            time.sleep(0.25 if key else 1.0)
    status["openalex"] = f"完成 {done} 篇"
    return done
