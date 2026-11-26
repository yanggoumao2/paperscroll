"""Fetch paper metadata from the arXiv API (export.arxiv.org) and upsert it."""
from __future__ import annotations

import json
import logging
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

import httpx

from . import db

log = logging.getLogger("paperscroll.arxiv")

API = "https://export.arxiv.org/api/query"
NS = {
    "a": "http://www.w3.org/2005/Atom",
    "arxiv": "http://arxiv.org/schemas/atom",
    "os": "http://a9.com/-/spec/opensearch/1.1/",
}
PAGE = 1000
DELAY = 3.2  # arXiv asks for >= 3 s between requests
UA = "paperscroll/0.1 (personal paper reader)"

_ID_RE = re.compile(r"arxiv\.org/abs/(.+?)(?:v(\d+))?$")


def _clean(s: str | None) -> str:
    return re.sub(r"\s+", " ", s or "").strip()


def parse_entry(e: ET.Element) -> dict | None:
    raw = e.findtext("a:id", default="", namespaces=NS)
    m = _ID_RE.search(raw)
    if not m:
        return None
    authors = []
    for a in e.findall("a:author", NS):
        name = _clean(a.findtext("a:name", default="", namespaces=NS))
        aff = [_clean(x.text) for x in a.findall("arxiv:affiliation", NS) if x.text]
        authors.append({"name": name, "aff": aff})
    cats = [c.get("term") for c in e.findall("a:category", NS) if c.get("term")]
    prim = e.find("arxiv:primary_category", NS)
    return {
        "id": m.group(1),
        "version": int(m.group(2) or 1),
        "title": _clean(e.findtext("a:title", namespaces=NS)),
        "abstract": _clean(e.findtext("a:summary", namespaces=NS)),
        "authors": authors,
        "categories": cats,
        "primary_cat": prim.get("term") if prim is not None else (cats[0] if cats else ""),
        "published": e.findtext("a:published", default="", namespaces=NS),
        "updated": e.findtext("a:updated", default="", namespaces=NS),
        "comment": _clean(e.findtext("arxiv:comment", default="", namespaces=NS)),
        "journal_ref": _clean(e.findtext("arxiv:journal_ref", default="", namespaces=NS)),
        "doi": _clean(e.findtext("arxiv:doi", default="", namespaces=NS)),
    }


def _get(client: httpx.Client, params: dict) -> ET.Element:
    last = None
    for attempt in range(6):
        try:
            r = client.get(API, params=params, timeout=90)
            if r.status_code == 200:
                return ET.fromstring(r.content)
            last = f"HTTP {r.status_code}"
        except Exception as ex:  # network hiccup
            last = repr(ex)
        time.sleep(min(60, 5 * 2 ** attempt))
    raise RuntimeError(f"arXiv API failed: {last}")


def fetch_window(cats: list[str], start: datetime, end: datetime, progress=None):
    """Yield parsed entries submitted in [start, end] for any of `cats`."""
    q = "(" + " OR ".join(f"cat:{c}" for c in cats) + ")"
    q += f" AND submittedDate:[{start:%Y%m%d%H%M} TO {end:%Y%m%d%H%M}]"
    pos, total, empty_retries = 0, None, 0
    with httpx.Client(headers={"User-Agent": UA}, follow_redirects=True) as client:
        while True:
            root = _get(client, {"search_query": q, "start": pos, "max_results": PAGE,
                                 "sortBy": "submittedDate", "sortOrder": "descending"})
            total = int(root.findtext("os:totalResults", default="0", namespaces=NS))
            entries = root.findall("a:entry", NS)
            if not entries and pos < total and empty_retries < 3:
                empty_retries += 1          # arXiv sometimes returns a transient empty page
                time.sleep(DELAY * 3)
                continue
            empty_retries = 0
            for e in entries:
                p = parse_entry(e)
                if p:
                    yield p
            pos += len(entries)
            if progress:
                progress(pos, total)
            if not entries or pos >= total:
                break
            time.sleep(DELAY)
        time.sleep(DELAY)


UPSERT = """
INSERT INTO papers(id, version, title, abstract, authors, categories, primary_cat, published, updated,
                   comment, journal_ref, doi, added)
VALUES(:id, :version, :title, :abstract, :authors, :categories, :primary_cat, :published, :updated,
       :comment, :journal_ref, :doi, :added)
ON CONFLICT(id) DO UPDATE SET
  version=excluded.version, title=excluded.title, abstract=excluded.abstract, authors=excluded.authors,
  categories=excluded.categories, primary_cat=excluded.primary_cat, updated=excluded.updated,
  comment=excluded.comment, journal_ref=excluded.journal_ref, doi=excluded.doi,
  emb=CASE WHEN papers.abstract IS excluded.abstract AND papers.title IS excluded.title THEN papers.emb ELSE NULL END
WHERE excluded.version > papers.version
"""


def ingest(cats: list[str], since: datetime, until: datetime | None = None, progress=None) -> int:
    """Fetch [since, until] in 7-day slices (keeps each query under arXiv's result cap)."""
    until = until or datetime.now(timezone.utc)
    now_iso = datetime.now(timezone.utc).isoformat(timespec="seconds")
    n = 0
    slice_end = until
    while slice_end > since:
        slice_start = max(since, slice_end - timedelta(days=7))
        batch = []
        for p in fetch_window(cats, slice_start, slice_end,
                              progress=(lambda a, b, s=slice_start: progress and progress(f"{s:%m-%d} {a}/{b}"))):
            p["authors"] = json.dumps(p["authors"], ensure_ascii=False)
            p["categories"] = " ".join(p["categories"])
            p["added"] = now_iso
            batch.append(p)
            if len(batch) >= 500:
                with db.writer() as con:
                    con.executemany(UPSERT, batch)
                n += len(batch)
                batch = []
        if batch:
            with db.writer() as con:
                con.executemany(UPSERT, batch)
            n += len(batch)
        log.info("ingested slice %s..%s, total %d", slice_start.date(), slice_end.date(), n)
        slice_end = slice_start
    return n
