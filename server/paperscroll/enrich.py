"""Semantic Scholar enrichment (citations, venue, TL;DR) and venue parsing from arXiv comments."""
from __future__ import annotations

import logging
import re
import time
from datetime import datetime, timedelta, timezone

import httpx

from . import config, db

log = logging.getLogger("paperscroll.s2")

S2_BATCH = "https://api.semanticscholar.org/graph/v1/paper/batch"
FIELDS = "citationCount,venue,publicationVenue,tldr"
BATCH = 400

VENUES = (r"NeurIPS|NIPS|ICML|ICLR|CVPR|ICCV|ECCV|WACV|BMVC|3DV|AAAI|IJCAI|ACL|EMNLP|NAACL|COLING|EACL|COLM|"
          r"CoRL|RSS|ICRA|IROS|Humanoids|CASE|T-?RO|RA-?L|IJRR|TPAMI|IJCV|TIP|TMLR|JMLR|KDD|WWW|SIGIR|WSDM|"
          r"RecSys|CIKM|SIGGRAPH(?: Asia)?|TOG|Interspeech|ICASSP|TASLP|MICCAI|CHI|UIST|ACM MM|MM|AISTATS|UAI|"
          r"COLT|ISMIR|L4DC|ECAI|ICME|ICIP")
VENUE_RE = re.compile(rf"\b({VENUES})\b[\s'’]*((?:20)?\d\d)?", re.I)
ACCEPT_RE = re.compile(r"\b(accepted|to appear|published|camera[- ]ready|oral|spotlight|poster|in proceedings)\b", re.I)
NOT_ACCEPT_RE = re.compile(r"\b(submitted|under review|in submission|preprint)\b", re.I)


def comment_venue(comment: str, journal_ref: str) -> tuple[str, bool]:
    """Return (venue label, accepted?) parsed from arXiv comment / journal_ref."""
    text = f"{comment or ''} ; {journal_ref or ''}"
    m = VENUE_RE.search(text)
    label = ""
    if m:
        name = m.group(1)
        canon = {v.lower(): v for v in VENUES.replace("(?: Asia)?", "").replace("-?", "-").split("|")}
        name = canon.get(name.lower(), name)
        year = m.group(2) or ""
        if len(year) == 2:
            year = "20" + year
        label = f"{name} {year}".strip()
    accepted = bool(journal_ref) or (bool(ACCEPT_RE.search(comment or "")) and not NOT_ACCEPT_RE.search(comment or ""))
    if label and not accepted and NOT_ACCEPT_RE.search(comment or ""):
        label = ""  # "submitted to CVPR" is not a venue badge
    return label, accepted


def _post(client: httpx.Client, ids: list[str], key: str):
    headers = {"x-api-key": key} if key else {}
    for attempt in range(9):
        try:
            r = client.post(S2_BATCH, params={"fields": FIELDS}, json={"ids": [f"ARXIV:{i}" for i in ids]},
                            headers=headers, timeout=60)
            if r.status_code == 200:
                return r.json()
            if r.status_code not in (429, 500, 502, 503, 504):
                log.warning("S2 HTTP %s: %s", r.status_code, r.text[:200])
                return None
        except Exception as ex:
            log.info("S2 error %r", ex)
        time.sleep(min(120, 3 * 2 ** attempt))   # exponential backoff on 429 / 5xx
    return None


def enrich_pending(stop_event, status) -> int:
    """Enrich papers never enriched, or enriched > 7 days ago (citations change). Returns count."""
    cfg = config.load()
    key = cfg.get("s2_api_key") or ""
    gap = 1.1 if key else 3.5
    stale = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat(timespec="seconds")
    con = db.connect()
    ids = [r["id"] for r in con.execute(
        "SELECT id FROM papers WHERE s2_at IS NULL OR s2_at < ? ORDER BY (s2_at IS NOT NULL), published DESC",
        (stale,))]
    con.close()
    done = 0
    with httpx.Client(follow_redirects=True) as client:
        for i in range(0, len(ids), BATCH):
            if stop_event.is_set():
                break
            chunk = ids[i:i + BATCH]
            res = _post(client, chunk, key)
            if res is None:
                status["s2"] = f"rate-limited, {done}/{len(ids)} done; retry later"
                break
            now = datetime.now(timezone.utc).isoformat(timespec="seconds")
            rows = []
            for pid, item in zip(chunk, res):
                if not item:
                    rows.append((now, None, None, None, pid))
                    continue
                tl = (item.get("tldr") or {}).get("text")
                venue = item.get("venue") or ((item.get("publicationVenue") or {}).get("name")) or ""
                if venue.lower() in ("arxiv.org", "arxiv", "corr"):
                    venue = ""
                rows.append((now, tl, venue, item.get("citationCount"), pid))
            with db.writer() as w:
                w.executemany("UPDATE papers SET s2_at=?, tldr=COALESCE(?, tldr), venue=?, "
                              "citations=COALESCE(?, citations) WHERE id=?", rows)
            done += len(chunk)
            status["s2"] = f"{done}/{len(ids)}"
            time.sleep(gap)
    return done
