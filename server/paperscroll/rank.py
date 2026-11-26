"""Profile (topic + Rocchio feedback) and feed ranking: hybrid BM25 + embedding + recency/quality/novelty."""
from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone

import numpy as np

from . import db, glance, tiers
from .embed import INDEX, encode
from .enrich import comment_venue

DEFAULT_PREFS = {"recency": "fresh", "fit": "balanced", "quality": "all", "novelty": "balanced"}

STOP = set("""a an the and or of for in on to with without by from via using use based towards toward into
over under than this that these those is are be we our their its as at it new novel approach method methods
model models paper study learning especially particularly about more less faster better efficient""".split())

CAT_NAMES = {
    "cs.AI": "AI", "cs.LG": "机器学习", "cs.CV": "视觉", "cs.CL": "NLP", "cs.RO": "机器人", "cs.IR": "检索",
    "cs.SD": "声音", "eess.AS": "语音", "eess.IV": "图像视频", "cs.HC": "人机交互", "cs.MA": "多智能体",
    "cs.NE": "神经进化", "cs.GR": "图形学", "eess.SY": "控制", "cs.SY": "控制", "stat.ML": "统计学习",
}


# ---------------------------------------------------------------- profile

def get_profile() -> dict:
    raw = db.kv_get("profile")
    p = json.loads(raw) if raw else {"topic": "", "keywords": "", "prefs": dict(DEFAULT_PREFS)}
    p["prefs"] = {**DEFAULT_PREFS, **(p.get("prefs") or {})}
    return p


def set_profile(topic: str, keywords: str, prefs: dict) -> dict:
    old = get_profile()
    p = {"topic": topic.strip(), "keywords": keywords.strip(), "prefs": {**DEFAULT_PREFS, **(prefs or {})}}
    db.kv_set("profile", json.dumps(p, ensure_ascii=False))
    if (old.get("topic"), old.get("keywords")) != (p["topic"], p["keywords"]):
        db.kv_set("topic_vec", None)
    return p


def topic_vector(p: dict) -> np.ndarray | None:
    text = " ".join(x for x in (p.get("topic"), p.get("keywords")) if x)
    if not text:
        return None
    cached = db.kv_get("topic_vec")
    if cached:
        d = json.loads(cached)
        if d.get("text") == text:
            return np.array(d["v"], dtype=np.float32)
    v = encode([text])[0]
    db.kv_set("topic_vec", json.dumps({"text": text, "v": v.tolist()}))
    return v


def query_vector(p: dict) -> np.ndarray | None:
    """Rocchio: topic + 0.7*mean(liked/saved/commented) - 0.35*mean(not interested)."""
    q = topic_vector(p)
    con = db.connect()
    pos = [r["id"] for r in con.execute(
        "SELECT id FROM interactions WHERE liked=1 OR saved=1 OR (comment IS NOT NULL AND comment!='')")]
    neg = [r["id"] for r in con.execute("SELECT id FROM interactions WHERE hidden=1")]
    con.close()
    with INDEX.lock:
        P = [INDEX.M[INDEX.pos[i]] for i in pos if i in INDEX.pos]
        N = [INDEX.M[INDEX.pos[i]] for i in neg if i in INDEX.pos]
    if q is None and not P:
        return None
    v = np.zeros(INDEX.M.shape[1] if INDEX.M.size else 384, dtype=np.float32) if q is None else q.copy()
    if P:
        v += 0.7 * np.mean(P, axis=0)
    if N:
        v -= 0.35 * np.mean(N, axis=0)
    return v / max(np.linalg.norm(v), 1e-9)


def fts_query(p: dict) -> str:
    terms = []
    for kw in re.split(r"[,，;；\n]", p.get("keywords") or ""):
        kw = kw.strip()
        if kw and re.search(r"[A-Za-z]", kw):
            terms.append('"' + kw.replace('"', "") + '"')
    for w in re.findall(r"[A-Za-z][A-Za-z0-9\-]{2,}", p.get("topic") or ""):
        if w.lower() not in STOP:
            terms.append('"' + w + '"')
    return " OR ".join(dict.fromkeys(terms))


def bm25_scores(p: dict, limit: int = 1500) -> dict[str, float]:
    q = fts_query(p)
    if not q:
        return {}
    con = db.connect()
    try:
        rows = con.execute(
            "SELECT papers.id AS id, bm25(fts, 3.0, 1.0) AS s FROM fts JOIN papers ON papers.rid = fts.rowid "
            "WHERE fts MATCH ? ORDER BY s LIMIT ?", (q, limit)).fetchall()
    except Exception:
        rows = []
    finally:
        con.close()
    if not rows:
        return {}
    best = -rows[0]["s"] or 1.0
    return {r["id"]: max(0.0, -r["s"] / best) for r in rows}


# ---------------------------------------------------------------- feed

def feed(n: int = 6, window_days: int = 90, pin: str | None = None) -> tuple[list[str], set[str], dict]:
    """Pick the next batch; returns (paper ids in display order, ids that are explore cards, why-recommended per id)."""
    p = get_profile()
    prefs = p["prefs"]
    q = query_vector(p)
    bm = bm25_scores(p)
    con = db.connect()
    excluded = {r["id"] for r in con.execute("SELECT id FROM seen")} | \
               {r["id"] for r in con.execute("SELECT id FROM interactions WHERE hidden=1")}
    con.close()

    with INDEX.lock:
        ids, M, pub, cites, acc = INDEX.ids, INDEX.M, INDEX.pub, INDEX.cites, INDEX.accepted
    if not ids:
        return ([pin] if pin else []), set(), {}
    now = time.time()
    age_days = (now - pub) / 86400.0
    mask = age_days <= window_days
    mask &= np.array([i not in excluded for i in ids])

    if q is not None:
        sem = M @ q
        sub = sem[mask] if mask.any() else sem
        semz = (sem - sub.mean()) / (sub.std() + 1e-6)
    else:
        semz = np.zeros(len(ids))
    bmv = np.array([bm.get(i, 0.0) for i in ids])

    fit = prefs["fit"]
    w_bm = {"strict": 1.6, "balanced": 1.0, "broad": 0.5}.get(fit, 1.0)
    score = semz + w_bm * bmv

    rec = prefs["recency"]
    if rec == "newest":
        score += 1.5 * np.exp(-age_days / 4.0)
        newest_mask = mask & (age_days <= 10)
        if newest_mask.sum() >= n * 3:
            mask = newest_mask
    elif rec == "fresh":
        score += 0.7 * np.exp(-age_days / 21.0)

    qual = prefs["quality"]
    if qual == "accepted":
        score += 0.9 * acc
    elif qual == "cited":
        score += 0.45 * np.log1p(cites)
    elif qual == "classic":
        score += 0.8 * np.log1p(cites)

    nov = prefs["novelty"]
    noise = {"stable": 0.0, "balanced": 0.2, "surprise": 0.55}.get(nov, 0.2)
    rng = np.random.default_rng()
    if noise:
        score = score + noise * rng.gumbel(size=len(score))

    if fit == "strict" and q is not None:
        mask &= (semz > 1.0) | (bmv > 0.2)
        if mask.sum() < n:   # never return an empty feed just because the filter is strict
            mask = (age_days <= window_days) & np.array([i not in excluded for i in ids])

    score = np.where(mask, score, -np.inf)
    n_explore = {"strict": 0, "balanced": 1, "broad": 2}.get(fit, 1) + (1 if nov == "surprise" else 0)
    n_explore = min(n_explore, max(0, n - 2))
    order = np.argsort(-score)
    main = [i for i in order[: n - n_explore] if np.isfinite(score[i])]

    explore: list[int] = []
    if n_explore and q is not None:
        # neighbouring topics: moderately similar papers (z between 0.8 and 1.8) not already picked
        cand = np.where(mask & (semz > 0.8) & (semz < 1.8))[0]
        cand = np.setdiff1d(cand, main)
        if len(cand):
            explore = list(rng.choice(cand, size=min(n_explore, len(cand)), replace=False))

    picked = [ids[i] for i in main]
    exp_ids = {ids[i] for i in explore}
    for k, e in enumerate(explore):   # interleave explore cards
        picked.insert(min(len(picked), 2 + k * 3), ids[e])
    if pin and pin not in picked:
        picked.insert(0, pin)

    # why each card was picked: semantic rank among candidates + which of the user's keywords it mentions
    why: dict[str, dict] = {}
    pool = semz[mask] if (q is not None and mask.any()) else None
    kws = [k.strip() for k in re.split(r"[,，;；]", p.get("keywords") or "") if k.strip()]
    pos = {pid: i for i, pid in enumerate(ids)}
    con = db.connect()
    for pid in picked:
        w: dict = {}
        i = pos.get(pid)
        if pool is not None and i is not None:
            w["top"] = round(max(0.1, float((pool > semz[i]).mean() * 100)), 1)
        if kws:
            r = con.execute("SELECT title, abstract FROM papers WHERE id=?", (pid,)).fetchone()
            if r:
                text = f"{r['title']} {r['abstract']}".lower()
                w["hits"] = [k for k in kws if k.lower() in text][:3]
        why[pid] = w
    con.close()

    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with db.writer() as w:
        w.executemany("INSERT OR IGNORE INTO seen(id, ts) VALUES(?,?)", [(i, stamp) for i in picked])
    return picked, exp_ids, why


# ---------------------------------------------------------------- cards

def _tldr_fallback(abstract: str) -> str:
    sents = re.split(r"(?<=[.!?])\s+(?=[A-Z])", abstract or "")
    out = ""
    for s in sents:
        if len(out) + len(s) > 330 and out:
            break
        out = (out + " " + s).strip()
    return out


def card(row, inter=None) -> dict:
    authors = json.loads(row["authors"] or "[]")
    names = [a["name"] for a in authors]
    affs = json.loads(row["affiliations"]) if row["affiliations"] else []
    if not affs:   # occasionally the arXiv API itself carries affiliations
        for a in authors:
            for x in a.get("aff") or []:
                if x not in affs:
                    affs.append(x)
    cv, accepted = comment_venue(row["comment"], row["journal_ref"])
    oa_venue = row["oa_venue"] if "oa_venue" in row.keys() else None
    if cv and re.search(r"\bfindings\b", row["comment"] or "", re.I):
        cv = "Findings of " + cv          # Findings tracks are not the main conference
    if oa_venue and "findings" in oa_venue.lower():
        cv = cv if cv.startswith("Findings") else ""
    src = cv or row["venue"] or oa_venue or ""
    t = tiers.lookup(src)
    year = re.search(r"\b20\d\d\b", src or "")
    if src and len(src) > 30 and not t["short"]:
        src = src[:28].rsplit(" ", 1)[0] + "…"
    venue = cv or ((t["short"] + (" " + year.group(0) if year else "")) if t["short"] else "") or src
    cats = (row["categories"] or "").split()
    pid = row["id"]
    g = glance.analyze(row["title"], row["abstract"], row["comment"])
    return {
        "id": pid,
        "title": g["title"],
        "glance": {k: g[k] for k in ("problem", "method", "result", "name", "kinds", "code", "project", "code_soon", "pages", "figures")},
        "sents": g["sents"], "roles": g["roles"],
        "tldr": glance.clean(row["tldr"] or _tldr_fallback(row["abstract"])),
        "tldr_src": "s2" if row["tldr"] else "abstract",
        "abstract": glance.clean(row["abstract"]),
        "authors": names,
        "n_authors": len(names),
        "first_author": names[0] if names else "",
        "last_author": names[-1] if len(names) > 1 else "",
        "affiliations": affs[:4],
        "venue": venue,
        "accepted": bool(accepted or row["venue"] or oa_venue),
        "tier": {"ccf": t["ccf"], "core": t["core"]},
        "citations": row["citations"],
        "primary": row["primary_cat"],
        "tags": [CAT_NAMES.get(c, c) for c in cats[:4]],
        "categories": cats,
        "published": (row["published"] or "")[:10],
        "comment": row["comment"],
        "has_fig": row["fig_state"] == 1,
        "fig_state": row["fig_state"],
        # state 0/3 = not looked up yet / transient error: let the image endpoint try lazily
        "fig": f"/api/img/{pid}" if row["fig_state"] in (0, 1, 3) else None,
        "arxiv_url": f"https://arxiv.org/abs/{pid}",
        "pdf_url": f"https://arxiv.org/pdf/{pid}",
        "html_url": f"https://arxiv.org/html/{pid}",
        "doi": row["doi"],
        "liked": bool(inter and inter["liked"]),
        "saved": bool(inter and inter["saved"]),
        "hidden": bool(inter and inter["hidden"]),
        "note": (inter["comment"] if inter else None) or "",
    }


def cards_for(pids: list[str]) -> list[dict]:
    if not pids:
        return []
    con = db.connect()
    q = ",".join("?" * len(pids))
    rows = {r["id"]: r for r in con.execute(f"SELECT * FROM papers WHERE id IN ({q})", pids)}
    inters = {r["id"]: r for r in con.execute(f"SELECT * FROM interactions WHERE id IN ({q})", pids)}
    con.close()
    return [card(rows[i], inters.get(i)) for i in pids if i in rows]
