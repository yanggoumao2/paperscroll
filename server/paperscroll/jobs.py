"""Background pipeline: arXiv ingest -> local embeddings -> index reload -> prune -> S2 enrichment.
Runs once at startup if needed, then at the configured local times (default 12:35 and 23:30)."""
from __future__ import annotations

import json
import logging
import threading
import time
from datetime import datetime, timedelta, timezone

from . import arxiv, config, db, embed, enrich, openalex

log = logging.getLogger("paperscroll.jobs")

STATUS: dict = {"state": "idle", "step": "", "ingest": "", "embed": "", "s2": "", "openalex": "", "last_sync": None,
                "last_error": None}
_stop = threading.Event()
_run_lock = threading.Lock()


def _utc(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def run_pipeline(full: bool = False) -> None:
    if not _run_lock.acquire(blocking=False):
        return
    try:
        cfg = config.load()
        cats = cfg["categories"]
        window = int(cfg["window_days"])
        now = datetime.now(timezone.utc)
        STATUS.update(state="running", last_error=None)

        synced_cats = set(json.loads(db.kv_get("synced_cats") or "[]"))
        new_cats = [c for c in cats if c not in synced_cats]
        old_cats = [c for c in cats if c in synced_cats]
        con = db.connect()
        latest = con.execute("SELECT MAX(published) AS m FROM papers").fetchone()["m"]
        con.close()

        STATUS["step"] = "arXiv"
        prog = lambda s: STATUS.__setitem__("ingest", s)
        if new_cats:      # first run or newly added categories: backfill the whole window
            arxiv.ingest(new_cats, now - timedelta(days=window), now, progress=prog)
            db.kv_set("synced_cats", json.dumps(sorted(synced_cats | set(new_cats))))
        if old_cats:      # incremental: from 3 days before the newest paper we have
            since = (_utc(latest) - timedelta(days=3)) if (latest and not full) else now - timedelta(days=window)
            arxiv.ingest(old_cats, since, now, progress=prog)

        STATUS["step"] = "embedding"
        embed.embed_pending(_stop, STATUS)

        STATUS["step"] = "pruning"
        cutoff = (now - timedelta(days=window + 2)).isoformat()
        with db.writer() as w:
            w.execute("DELETE FROM papers WHERE published < ? AND id NOT IN "
                      "(SELECT id FROM interactions WHERE liked=1 OR saved=1 OR comment IS NOT NULL)", (cutoff,))
        embed.INDEX.reload()

        STATUS["last_sync"] = datetime.now().isoformat(timespec="minutes")
        db.kv_set("last_sync", STATUS["last_sync"])

        STATUS["step"] = "OpenAlex"
        openalex.enrich_pending(_stop, STATUS)
        embed.INDEX.reload()

        STATUS["step"] = "Semantic Scholar"
        enrich.enrich_pending(_stop, STATUS)
        embed.INDEX.reload()   # citation/venue features changed
        STATUS.update(state="idle", step="")
    except Exception as ex:
        log.exception("pipeline failed")
        STATUS.update(state="error", last_error=repr(ex))
    finally:
        _run_lock.release()


def trigger(full: bool = False) -> bool:
    if _run_lock.locked():
        return False
    threading.Thread(target=run_pipeline, args=(full,), daemon=True).start()
    return True


def _scheduler() -> None:
    fired: set[str] = set()
    while not _stop.is_set():
        cfg = config.load()
        now = datetime.now()
        key = now.strftime("%Y-%m-%d %H:%M")
        if now.strftime("%H:%M") in cfg.get("sync_times", []) and key not in fired:
            fired.add(key)
            trigger()
        _stop.wait(20)


def start() -> None:
    STATUS["last_sync"] = db.kv_get("last_sync")
    embed.INDEX.reload()
    threading.Thread(target=embed.model, daemon=True).start()   # warm the model so the first topic is fast
    threading.Thread(target=_scheduler, daemon=True).start()
    # catch up on start: never synced, categories changed, or last sync > 12 h ago
    last = STATUS["last_sync"]
    stale = (not last) or (datetime.now() - datetime.fromisoformat(last) > timedelta(hours=12))
    synced = set(json.loads(db.kv_get("synced_cats") or "[]"))
    if stale or set(config.load()["categories"]) - synced:
        trigger()


def stop() -> None:
    _stop.set()
