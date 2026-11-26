"""Local multilingual sentence embeddings (fastembed / ONNX, CPU) and the in-memory vector index."""
from __future__ import annotations

import logging
import threading

import numpy as np

from . import config, db

log = logging.getLogger("paperscroll.embed")

_model = None
_model_lock = threading.Lock()


def model():
    global _model
    with _model_lock:
        if _model is None:
            import os
            from fastembed import TextEmbedding
            # leave CPU headroom so the API stays responsive while a sync is embedding
            threads = max(1, (os.cpu_count() or 4) // 2)
            _model = TextEmbedding(config.EMBED_MODEL, cache_dir=str(config.MODEL_DIR), threads=threads)
        return _model


def _norm(v: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(v, axis=-1, keepdims=True)
    return (v / np.maximum(n, 1e-9)).astype(np.float32)


def encode(texts: list[str]) -> np.ndarray:
    return _norm(np.array(list(model().embed(texts, batch_size=64)), dtype=np.float32))


def doc_text(title: str, abstract: str) -> str:
    return f"{title}. {(abstract or '')[:1200]}"


def embed_pending(stop_event, status) -> int:
    con = db.connect()
    rows = con.execute("SELECT id, title, abstract FROM papers WHERE emb IS NULL").fetchall()
    con.close()
    total, done = len(rows), 0
    for i in range(0, total, 256):
        if stop_event.is_set():
            break
        chunk = rows[i:i + 256]
        vecs = encode([doc_text(r["title"], r["abstract"]) for r in chunk])
        with db.writer() as w:
            w.executemany("UPDATE papers SET emb=? WHERE id=?",
                          [(v.tobytes(), r["id"]) for v, r in zip(vecs, chunk)])
        done += len(chunk)
        status["embed"] = f"{done}/{total}"
    return done


class Index:
    """All embedded papers in the window as a matrix, plus per-paper ranking features."""

    def __init__(self):
        self.lock = threading.Lock()
        self.ids: list[str] = []
        self.pos: dict[str, int] = {}
        self.M = np.zeros((0, 384), dtype=np.float32)
        self.pub = np.zeros(0)          # unix seconds
        self.cites = np.zeros(0)
        self.accepted = np.zeros(0, dtype=np.float64)

    def reload(self) -> None:
        from datetime import datetime
        from .enrich import comment_venue
        from .tiers import lookup
        con = db.connect()
        rows = con.execute("SELECT id, emb, published, citations, comment, journal_ref, venue, oa_venue "
                           "FROM papers WHERE emb IS NOT NULL").fetchall()
        con.close()
        ids, vecs, pub, cites, acc = [], [], [], [], []
        for r in rows:
            ids.append(r["id"])
            vecs.append(np.frombuffer(r["emb"], dtype=np.float32))
            try:
                pub.append(datetime.fromisoformat(r["published"].replace("Z", "+00:00")).timestamp())
            except Exception:
                pub.append(0.0)
            cites.append(r["citations"] or 0)
            cv, a = comment_venue(r["comment"], r["journal_ref"])
            src = cv or r["venue"] or r["oa_venue"] or ""
            t = lookup(src) if src else {}
            top = t.get("ccf") == "A" or t.get("core") == "A*"
            # 0 = preprint, 1 = accepted somewhere, 1.5 = CCF-A / CORE A* venue
            acc.append((1.5 if top else 1.0) if (a or r["venue"] or r["oa_venue"]) else 0.0)
        with self.lock:
            self.ids = ids
            self.pos = {k: i for i, k in enumerate(ids)}
            self.M = np.vstack(vecs) if vecs else np.zeros((0, 384), dtype=np.float32)
            self.pub = np.array(pub)
            self.cites = np.array(cites, dtype=np.float64)
            self.accepted = np.array(acc, dtype=np.float64)
        log.info("index reloaded: %d papers", len(ids))


INDEX = Index()
