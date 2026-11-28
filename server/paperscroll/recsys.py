"""Recommender v2, modelled on how short-video feeds work (public descriptions of TikTok's "For You" feed and
ByteDance's Monolith paper), scaled down to one user on one machine:

1. Implicit feedback: every card's dwell time is compared with *your* usual dwell; quick skips count slightly
   against a paper, long reads, opening the figure / close reading / links count for it; likes, saves and notes
   count most. Older feedback fades (half-life 14 days).
2. Multiple interests: papers you engaged with are clustered (weighted spherical k-means); each cluster is a
   separate retrieval channel, so two unrelated interests are not averaged into a vector that matches neither.
3. Several recall channels: every interest, your written topic/keywords, the current session, authors you liked,
   and exploration.
4. A Thompson-sampling bandit decides how many cards each channel gets: channels whose cards you recently read
   get more, channels you keep skipping get fewer, untried ones are still sampled now and then.
5. Ranking within a channel: a hand-set linear score whose non-personal weights (recency, citations, venue,
   keyword match, topic match) are refined online by a regularised logistic regression on your own feedback.
6. Diversity: near-duplicates in a batch are dropped, and a skip streak in the current session raises exploration.

Everything is numpy over the existing embedding index; no model download, no network.
"""
from __future__ import annotations

import json
import math
import re
import time
from collections import Counter
from datetime import datetime

import numpy as np

from . import db
from .embed import INDEX

HALF_LIFE_D = 14.0
SESSION_S = 45 * 60
SKIP_S = 1.5            # same threshold the app uses for "skip"
DWELL_CAP = 120.0       # longer than this: the phone was probably put down
ENGAGE = {"fig": 0.8, "read": 1.0, "link": 1.0, "share": 1.2}
MAX_K = 6
LAST: dict = {}          # diagnostics of the last recommend() call

STOP = set("""a an the and or of for in on to with without by from via using use based towards toward into over under
than this that these those is are be we our their its as at it new novel approach method methods model models paper
study learning towards beyond through large scale efficient robust improving improved simple general can do does
what when where how why your you all one two via unified framework benchmark data dataset task tasks system systems
deep neural network networks bridging rethinking revisiting enabling leveraging scalable aware driven guided free
toward zero-shot end-to-end""".split())


def _ts(s: str | None) -> float:
    if not s:
        return 0.0
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return 0.0


# ---------------------------------------------------------------- feedback → reward per paper

def load_feedback(before: float | None = None) -> dict:
    """Aggregate events + explicit flags into one decayed reward per paper.

    Returns {"reward": {pid: r}, "served": {pid: ts}, "session": [(ts, pid, r)], "median": dwell, "now": t}."""
    now = before or time.time()
    con = db.connect()
    ev = con.execute("SELECT ts, id, kind, dwell FROM events").fetchall()
    inter = con.execute("SELECT id, liked, saved, hidden, comment, liked_at, saved_at, updated FROM interactions").fetchall()
    seen = con.execute("SELECT id, ts FROM seen").fetchall()
    con.close()

    evs, dup = [], set()
    for r in ev:   # older app versions could resend an event; identical dwell to the millisecond = same event
        t = _ts(r["ts"])
        if not t or t >= now:
            continue
        if r["kind"] in ("view", "skip", "fig", "read", "link", "share"):
            key = (r["id"], r["kind"], round(r["dwell"] or 0, 3)) if r["kind"] in ("view", "skip") else (r["id"], r["kind"])
            if key in dup:
                continue
            dup.add(key)
        evs.append((t, r["id"], r["kind"], r["dwell"]))
    views = [min(d, DWELL_CAP) for t, _, k, d in evs if k == "view" and d]
    med = float(np.median(views)) if len(views) >= 8 else 12.0
    med = max(4.0, med)

    decay = lambda t: 0.5 ** (max(0.0, now - t) / 86400.0 / HALF_LIFE_D)
    reward: dict[str, float] = {}
    engaged: Counter = Counter()
    session: list[tuple[float, str, float]] = []
    for t, pid, kind, dwell in evs:
        r = 0.0
        if kind == "skip":
            r = -0.4
        elif kind == "view":
            d = min(float(dwell or SKIP_S), DWELL_CAP)
            r = float(np.clip(0.3 + 0.6 * math.log(d / med), -0.3, 1.5))
        elif kind in ENGAGE and engaged[(pid, kind)] < 2:
            engaged[(pid, kind)] += 1
            r = ENGAGE[kind]
        else:
            continue
        reward[pid] = reward.get(pid, 0.0) + r * decay(t)
        if now - t < SESSION_S:
            session.append((t, pid, r))
    for r in inter:   # final explicit state (so un-like really removes the like)
        t = _ts(r["updated"]) or now
        if before and t >= now:
            continue
        x = 3.0 * (r["liked"] or 0) + 3.0 * (r["saved"] or 0) + (2.5 if (r["comment"] or "").strip() else 0.0)
        x -= 3.0 * (r["hidden"] or 0)
        if x:
            reward[r["id"]] = reward.get(r["id"], 0.0) + x * max(0.5, decay(t))   # explicit signals fade to half at most
    served = {r["id"]: _ts(r["ts"]) for r in seen if _ts(r["ts"]) < now}
    session.sort()
    return {"reward": reward, "served": served, "session": session, "median": med, "now": now}


# ---------------------------------------------------------------- interests

def _kmeans(X: np.ndarray, w: np.ndarray, k: int, seed: int = 0, iters: int = 25) -> np.ndarray:
    """Weighted spherical k-means with k-means++ init; returns unit centroids (k, d)."""
    rng = np.random.default_rng(seed)
    C = [X[int(np.argmax(w))]]
    for _ in range(1, k):
        d = 1.0 - np.max(X @ np.array(C).T, axis=1)
        p = np.maximum(d, 0) * w
        if p.sum() <= 0:
            break
        C.append(X[rng.choice(len(X), p=p / p.sum())])
    C = np.array(C)
    for _ in range(iters):
        a = np.argmax(X @ C.T, axis=1)
        new = []
        for j in range(len(C)):
            m = a == j
            v = (X[m] * w[m, None]).sum(0) if m.any() else C[j]
            new.append(v / max(np.linalg.norm(v), 1e-9))
        new = np.array(new)
        if np.allclose(new, C, atol=1e-5):
            break
        C = new
    return C.astype(np.float32)


_title_df: dict | None = None


def _df() -> tuple[Counter, int]:
    """Document frequency of title words over a fixed sample of the library (for interest labels)."""
    global _title_df
    if _title_df is None or time.time() - _title_df["t"] > 86400:
        con = db.connect()
        titles = [r[0] for r in con.execute("SELECT title FROM papers ORDER BY rid DESC LIMIT 6000")]
        con.close()
        c = Counter()
        for t in titles:
            c.update(set(_words(t)))
        _title_df = {"t": time.time(), "c": c, "n": max(1, len(titles))}
    return _title_df["c"], _title_df["n"]


def _words(title: str) -> list[str]:
    out = []
    for w in re.findall(r"[A-Za-z][A-Za-z0-9\-]{2,}", title or ""):
        lw = w.lower()
        if lw in STOP or len(lw) < 3:
            continue
        out.append(w if (w.isupper() and len(w) <= 6) else lw)
    return out


def _label(titles: list[str], common: set[str] = frozenset()) -> str:
    """Two distinctive title words; words shared by most of your liked papers (e.g. "manipulation") are skipped
    because they would not tell two interests apart."""
    df, n = _df()
    tf = Counter()
    for t in titles:
        tf.update(w for w in set(_words(t)) if w.lower() not in common)
    scored = sorted(tf, key=lambda w: -(tf[w] * math.log((n + 1) / (1 + df.get(w, df.get(w.lower(), 0))))))
    picked: list[str] = []
    for w in scored:
        if tf[w] < min(2, len(titles)) or any(w.lower()[:5] == x.lower()[:5] for x in picked):
            continue
        picked.append(w)
        if len(picked) == 2:
            break
    picked = picked or scored[:1]
    return " · ".join(picked)


def interests(fb: dict) -> list[dict]:
    """Cluster the papers with positive feedback into up to MAX_K interests."""
    pos = [(pid, r) for pid, r in fb["reward"].items() if r > 0.3 and pid in INDEX.pos]
    if not pos:
        return []
    with INDEX.lock:
        X = np.array([INDEX.M[INDEX.pos[p]] for p, _ in pos])
    w = np.array([min(r, 6.0) for _, r in pos])
    k = int(np.clip(round(math.sqrt(len(pos) / 2)), 1, MAX_K))
    C = _kmeans(X, w, k)
    a = np.argmax(X @ C.T, axis=1)
    con = db.connect()
    title = {}
    q = ",".join("?" * len(pos))
    for r in con.execute(f"SELECT id, title FROM papers WHERE id IN ({q})", [p for p, _ in pos]):
        title[r[0]] = r[1]
    con.close()
    common: set[str] = set()
    if k > 1:
        cnt = Counter(w.lower() for p, _ in pos for w in set(_words(title.get(p, ""))))
        common = {w for w, c in cnt.items() if c >= 0.35 * len(pos)}
    out = []
    for j in range(len(C)):
        sel = np.where(a == j)[0]
        members = [pos[i][0] for i in sel]
        mass = float(w[sel].sum())
        if not members or (len(members) == 1 and mass < 1.5):   # one long look is not an interest yet
            continue
        out.append({"c": C[j], "mass": mass, "members": members,
                    "label": _label([title.get(m, "") for m in members], common)})
    out.sort(key=lambda x: -x["mass"])
    return out


def interest_sims(ints: list[dict], M: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """(N, k) z-scored similarity of every paper to each interest: the mean of its two closest member papers
    (item-to-item, like "more like the ones you watched"). Tighter than one centroid, which for a few unrelated
    members points somewhere between them."""
    if not ints:
        return np.zeros((len(M), 0))
    pos = INDEX.pos
    cols = []
    for x in ints:
        X = np.array([M[pos[m]] for m in x["members"] if m in pos])
        S = M @ X.T
        if S.shape[1] >= 2:
            top2 = np.partition(S, -2, axis=1)[:, -2:]
            s = top2.mean(axis=1)
        else:
            s = S[:, 0]
        cols.append(_z(s, mask))
    return np.stack(cols, axis=1)


# ---------------------------------------------------------------- online ranker (non-personal weights)

# feature order for the learned part
# ("topic" is not learned: every paper you were shown was already picked for topic match, so among them topic
#  similarity cannot predict reading — learning it would only drive its weight to zero.)
LEARN = ["bm25", "recent", "cites", "accepted", "author"]


def fit_weights(rows: np.ndarray, y: np.ndarray, w0: np.ndarray, lam: float = 4.0, iters: int = 300) -> np.ndarray:
    """MAP logistic regression whose weights are pulled towards the hand-set ones (Gaussian prior around w0).
    Few labels → stays at w0; consistent feedback → moves. Returns weights (bias first)."""
    if len(y) < 12 or y.min() == y.max():
        return np.concatenate([[0.0], w0])
    Xb = np.hstack([np.ones((len(rows), 1)), rows])
    prior = np.concatenate([[0.0], w0])
    reg = np.array([0.0] + [lam] * len(w0))
    w = prior.copy()
    for _ in range(iters):   # Newton steps would be overkill at this size; plain gradient descent converges
        p = 1 / (1 + np.exp(-(Xb @ w)))
        g = Xb.T @ (p - y) / len(y) + reg * (w - prior) / len(y)
        w -= 0.5 * g
    return w


# ---------------------------------------------------------------- the feed

def _z(v: np.ndarray, mask: np.ndarray) -> np.ndarray:
    sub = v[mask] if mask.any() else v
    return (v - sub.mean()) / (sub.std() + 1e-6)


def features(q_topic, bm: dict, prefs: dict, author_ids: set, mask: np.ndarray) -> dict[str, np.ndarray]:
    with INDEX.lock:
        ids, M, pub, cites, acc = INDEX.ids, INDEX.M, INDEX.pub, INDEX.cites, INDEX.accepted
    age = (time.time() - pub) / 86400.0
    f = {
        "topic": _z(M @ q_topic, mask) if q_topic is not None else np.zeros(len(ids)),
        "bm25": np.array([bm.get(i, 0.0) for i in ids]),
        "recent": np.exp(-age / (4.0 if prefs.get("recency") == "newest" else 21.0)),
        "cites": np.log1p(cites),
        "accepted": acc,
        "author": np.array([1.0 if i in author_ids else 0.0 for i in ids]),
    }
    return f


def base_weights(prefs: dict) -> np.ndarray:
    fit, rec, qual = prefs.get("fit"), prefs.get("recency"), prefs.get("quality")
    w = {"bm25": {"strict": 1.6, "balanced": 1.0, "broad": 0.5}.get(fit, 1.0),
         "recent": {"newest": 1.5, "fresh": 0.7}.get(rec, 0.2),
         "cites": {"cited": 0.45, "classic": 0.8}.get(qual, 0.1),
         "accepted": {"accepted": 0.9}.get(qual, 0.2),
         "author": 0.8}
    return np.array([w[k] for k in LEARN])


def liked_authors(fb: dict) -> tuple[set, dict]:
    """Papers in the index by first/last authors of strongly positive papers → {pid}, {pid: author}."""
    top = [p for p, r in fb["reward"].items() if r >= 2.5][:40]
    if not top:
        return set(), {}
    con = db.connect()
    q = ",".join("?" * len(top))
    names = []
    for r in con.execute(f"SELECT authors FROM papers WHERE id IN ({q})", top):
        a = [x["name"] for x in json.loads(r[0] or "[]")]
        names += a[:1] + a[-1:] if len(a) > 1 else a
    con.close()
    names = list(dict.fromkeys(n for n in names if len(n) > 4))[:24]
    by_author = _author_index()
    hit: dict[str, str] = {}
    for n in names:
        for pid in by_author.get(n, ()):
            if pid not in top:
                hit.setdefault(pid, n)
    return set(hit), hit


_authors: dict = {"n": -1, "idx": {}}


def _author_index() -> dict[str, list[str]]:
    """author name → paper ids, rebuilt when the index size changes (parsing 50k author lists takes ~1 s)."""
    if _authors["n"] != len(INDEX.ids):
        con = db.connect()
        idx: dict[str, list[str]] = {}
        for pid, a in con.execute("SELECT id, authors FROM papers"):
            for x in json.loads(a or "[]"):
                idx.setdefault(x["name"], []).append(pid)
        con.close()
        _authors.update(n=len(INDEX.ids), idx=idx)
    return _authors["idx"]


def thompson(arms: dict[str, tuple[float, float]], n: int, rng, scale: dict[str, float]) -> list[str]:
    out = []
    for _ in range(n):
        draws = {a: rng.beta(s, f) * scale.get(a, 1.0) for a, (s, f) in arms.items()}
        out.append(max(draws, key=draws.get))
    return out


def recommend(profile: dict, q_topic, bm: dict, n: int, window_days: int, excluded: set, rng=None) -> tuple[list[str], set, dict]:
    rng = rng or np.random.default_rng()
    prefs = profile["prefs"]
    fb = load_feedback()
    ints = interests(fb)
    with INDEX.lock:
        ids, M, pub = INDEX.ids, INDEX.M, INDEX.pub
    if not ids:
        return [], set(), {}
    N = len(ids)
    age = (time.time() - pub) / 86400.0
    mask = (age <= window_days) & np.array([i not in excluded for i in ids])
    if prefs.get("recency") == "newest" and (mask & (age <= 10)).sum() >= n * 3:
        mask &= age <= 10

    a_ids, a_name = liked_authors(fb)
    F = features(q_topic, bm, prefs, a_ids, mask)
    Xf = np.stack([F[k] for k in LEARN], axis=1)

    # learn the non-personal weights from served papers with clear outcomes
    w0 = base_weights(prefs)
    pos = INDEX.pos
    lab = [(pos[p], 1.0 if r > 0.3 else 0.0) for p, r in fb["reward"].items() if p in pos and (r > 0.3 or r < -0.2)]
    if lab:
        idx, y = map(np.array, zip(*lab))
        w = fit_weights(Xf[idx], y, w0)
    else:
        w = np.concatenate([[0.0], w0])
    w_topic = {"strict": 1.0, "balanced": 0.6, "broad": 0.3}.get(prefs.get("fit"), 0.6)
    generic = Xf @ w[1:] + w_topic * F["topic"]
    LAST["weights"] = {k: round(float(v), 2) for k, v in zip(["bias"] + LEARN, w)}

    # personal similarity: best matching interest, minus closeness to hidden / repeatedly skipped papers
    Sz = interest_sims(ints, M, mask)
    neg = [p for p, r in fb["reward"].items() if r < -0.8 and p in pos]
    negz = _z(M @ _unit(np.mean([M[pos[p]] for p in neg], axis=0)), mask) if neg else np.zeros(N)

    # session: what you have been reading in the last 45 minutes
    sess_pos = [(p, r) for _, p, r in fb["session"] if r > 0.3 and p in pos]
    sessz = None
    if len(sess_pos) >= 2:
        sv = _unit(np.sum([M[pos[p]] * r for p, r in sess_pos], axis=0))
        sessz = _z(M @ sv, mask)
    recent_kinds = [r for _, _, r in fb["session"][-6:]]
    skip_streak = len(recent_kinds) >= 4 and sum(r < 0 for r in recent_kinds[-5:]) >= 4

    noise = {"stable": 0.0, "balanced": 0.15, "surprise": 0.4}.get(prefs.get("novelty"), 0.15)

    def channel_scores(arm: str) -> np.ndarray:
        if arm.startswith("i"):
            j = int(arm[1:])
            s = 1.3 * Sz[:, j] + 0.3 * F["topic"] + generic
        elif arm == "topic":
            s = 1.2 * F["topic"] + generic + 0.5 * F["bm25"]
        elif arm == "session":
            s = 1.3 * sessz + 0.3 * F["topic"] + generic
        elif arm == "author":
            s = np.where(F["author"] > 0, generic + 2.0 + (Sz.max(axis=1) if Sz.shape[1] else 0), -np.inf)
        else:   # explore: moderately related papers, not the closest ones
            near = Sz.max(axis=1) if Sz.shape[1] else F["topic"]
            band = (near > 0.4) & (near < 1.6)
            s = np.where(band, generic + rng.gumbel(size=N), -np.inf)
        s = s - 0.6 * np.maximum(negz, 0)
        if noise:
            s = s + noise * rng.gumbel(size=N)
        return np.where(mask, s, -np.inf)

    # bandit over channels: success = served card that got positive feedback, failure = skipped / hidden
    arms: dict[str, list[float]] = {}
    has_topic = q_topic is not None or bool(bm)
    for j in range(len(ints)):
        arms[f"i{j}"] = [1.0 + 0.4 * min(len(ints[j]["members"]), 5), 1.0]
    if has_topic:
        arms["topic"] = [2.0, 1.0]
    if sessz is not None:
        arms["session"] = [3.0, 1.0]
    if a_ids:
        arms["author"] = [1.0, 1.5]
    arms["explore"] = [1.0, 1.0]
    if len(arms) == 1 and not has_topic:   # brand-new user without a topic: recent papers
        arms["fresh"] = [2.0, 1.0]
    decay = lambda t: 0.5 ** (max(0.0, fb["now"] - t) / 86400.0 / 7.0)
    for p, t in fb["served"].items():
        if p not in pos:
            continue
        r = fb["reward"].get(p, 0.0)
        if -0.2 <= r <= 0.3:
            continue
        i = pos[p]
        if Sz.shape[1] and Sz[i].max() > 1.0:
            arm = f"i{int(np.argmax(Sz[i]))}"
        elif F["topic"][i] > 1.0 and has_topic:
            arm = "topic"
        else:
            arm = "explore"
        if arm in arms:
            arms[arm][0 if r > 0.3 else 1] += decay(t)
    explore_scale = {"stable": 0.35, "balanced": 0.6, "surprise": 0.9}.get(prefs.get("novelty"), 0.6)
    explore_scale *= {"strict": 0.4, "balanced": 1.0, "broad": 1.5}.get(prefs.get("fit"), 1.0)
    if skip_streak:
        explore_scale *= 1.8
    slots = thompson({k: tuple(v) for k, v in arms.items()}, n, rng, {"explore": explore_scale})

    picked: list[int] = []
    source: dict[int, str] = {}
    cache: dict[str, np.ndarray] = {}
    for arm in slots:
        if arm == "fresh":
            s = np.where(mask, F["recent"] + 0.3 * rng.gumbel(size=N), -np.inf)
        else:
            if arm not in cache:
                cache[arm] = channel_scores(arm)
            s = cache[arm]
        for i in np.argsort(-s)[:60]:
            if not np.isfinite(s[i]):
                break
            if i in source:
                continue
            if picked and float(np.max(M[picked] @ M[i])) > 0.92:   # near-duplicate of a card in this batch
                continue
            picked.append(int(i)); source[int(i)] = arm
            break
    if len(picked) < n:   # channels ran dry (tiny library): fill from the generic score
        s = np.where(mask, generic + F["topic"], -np.inf)
        for i in np.argsort(-s):
            if len(picked) >= n or not np.isfinite(s[i]):
                break
            if int(i) not in source:
                picked.append(int(i)); source[int(i)] = "fill"

    why: dict[str, dict] = {}
    explore_ids = set()
    pool_topic = F["topic"][mask] if mask.any() else F["topic"]
    for i in picked:
        pid, arm = ids[i], source[i]
        w_ = {}
        if arm.startswith("i"):
            w_ = {"reason": "interest", "label": ints[int(arm[1:])]["label"]}
        elif arm == "session":
            j = int(np.argmax(Sz[i])) if Sz.shape[1] else -1
            w_ = {"reason": "session", "label": ints[j]["label"] if j >= 0 else ""}
        elif arm == "author":
            w_ = {"reason": "author", "label": a_name.get(pid, "")}
        elif arm == "explore":
            explore_ids.add(pid)
            w_ = {"reason": "explore"}
        elif arm == "topic":
            w_ = {"reason": "topic"}
        if q_topic is not None:
            w_["top"] = round(max(0.1, float((pool_topic > F["topic"][i]).mean() * 100)), 1)
        why[pid] = w_
    return [ids[i] for i in picked], explore_ids, why


def offline_scores(profile: dict, q_topic, bm: dict, before: float) -> np.ndarray:
    """Personal relevance of every indexed paper using only feedback before `before` (for offline evaluation;
    the same terms the channels use, without the bandit, noise or batch rules)."""
    prefs = profile["prefs"]
    fb = load_feedback(before)
    ints = interests(fb)
    with INDEX.lock:
        M = INDEX.M
    N = len(M)
    mask = np.ones(N, dtype=bool)
    a_ids, _ = liked_authors(fb)
    F = features(q_topic, bm, prefs, a_ids, mask)
    Xf = np.stack([F[k] for k in LEARN], axis=1)
    w0 = base_weights(prefs)
    pos = INDEX.pos
    lab = [(pos[p], 1.0 if r > 0.3 else 0.0) for p, r in fb["reward"].items() if p in pos and (r > 0.3 or r < -0.2)]
    w = fit_weights(Xf[[i for i, _ in lab]], np.array([y for _, y in lab]), w0) if lab else np.concatenate([[0.0], w0])
    generic = Xf @ w[1:] + {"strict": 1.0, "balanced": 0.6, "broad": 0.3}.get(prefs.get("fit"), 0.6) * F["topic"]
    personal = 1.2 * F["topic"] + 0.5 * F["bm25"]
    if ints:
        Sz = interest_sims(ints, M, mask)
        personal = np.maximum(personal, 1.3 * Sz.max(axis=1))
    neg = [p for p, r in fb["reward"].items() if r < -0.8 and p in pos]
    if neg:
        personal -= 0.6 * np.maximum(_z(M @ _unit(np.mean([M[pos[p]] for p in neg], axis=0)), mask), 0)
    return personal + generic


def _unit(v):
    v = np.asarray(v, dtype=np.float32)
    return v / max(float(np.linalg.norm(v)), 1e-9)


def explain() -> dict:
    """What the recommender currently believes (for the settings page)."""
    fb = load_feedback()
    ints = interests(fb)
    return {"median_dwell": round(fb["median"], 1),
            "interests": [{"label": x["label"], "papers": len(x["members"]), "weight": round(x["mass"], 1)} for x in ints],
            "signals": len(fb["reward"])}
