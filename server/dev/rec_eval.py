"""Offline replay: does the recommender rank the papers you actually read above the ones you skipped?

Time split over your own history: feedback before the cut trains each scorer; every paper first shown after the
cut is a test case, labelled 1 if you read it (dwell >= your median view time, or liked/saved) and 0 if you only
skipped it. Reports ROC-AUC (0.5 = chance) with a bootstrap 95% interval for v1 (Rocchio) and v2.
Runs on a throw-away COPY of the database. Usage: rec_eval.py [cut_fraction=0.6]"""
import sys as _sys, pathlib as _pl
_sys.path.insert(0, str(_pl.Path(__file__).resolve().parents[1]))
import shutil, sqlite3, sys, tempfile
from pathlib import Path
import numpy as np
from paperscroll import config
tmp = Path(tempfile.gettempdir()) / "paperscroll-receval"; tmp.mkdir(exist_ok=True)
copy = tmp / "copy.db"
s = sqlite3.connect(f"file:{config.DB_PATH}?mode=ro", uri=True); d = sqlite3.connect(copy); s.backup(d); s.close(); d.close()
config.DB_PATH = copy
from paperscroll import db, rank, recsys
from paperscroll.embed import INDEX

INDEX.reload()
cut_frac = float(sys.argv[1]) if len(sys.argv) > 1 else 0.6
con = db.connect()
ev = [(recsys._ts(r["ts"]), r["id"], r["kind"], r["dwell"]) for r in con.execute("SELECT * FROM events ORDER BY ts")]
inter = {r["id"]: r for r in con.execute("SELECT * FROM interactions")}
con.close()
ev = [e for e in ev if e[2] in ("view", "skip")]
first = {}
for t, pid, k, dw in ev:
    first.setdefault(pid, t)
times = sorted(first.values())
cut = times[int(len(times) * cut_frac)]
med = recsys.load_feedback(cut)["median"]
label = {}
for t, pid, k, dw in ev:
    if first[pid] < cut:
        continue
    pos = (k == "view" and (dw or 0) >= med) or (pid in inter and (inter[pid]["liked"] or inter[pid]["saved"]))
    label[pid] = max(label.get(pid, 0), 1 if pos else 0)
test = [p for p in label if p in INDEX.pos]
y = np.array([label[p] for p in test])
print(f"events {len(ev)}, papers {len(first)}, cut at {cut_frac:.0%} → test {len(test)} papers ({int(y.sum())} read, {int((1-y).sum())} skipped), median dwell {med:.1f}s")

p = rank.get_profile()
q_topic = rank.topic_vector(p)
bm = rank.bm25_scores(p)


def v1_scores():
    """rank._feed_v1's score, with Rocchio positives/negatives restricted to before the cut."""
    v = q_topic.copy() if q_topic is not None else np.zeros(INDEX.M.shape[1], dtype=np.float32)
    P = [INDEX.M[INDEX.pos[i]] for i, r in inter.items() if i in INDEX.pos and recsys._ts(r["updated"]) < cut
         and (r["liked"] or r["saved"] or (r["comment"] or "").strip())]
    N = [INDEX.M[INDEX.pos[i]] for i, r in inter.items() if i in INDEX.pos and recsys._ts(r["updated"]) < cut and r["hidden"]]
    if P: v = v + 0.7 * np.mean(P, axis=0)
    if N: v = v - 0.35 * np.mean(N, axis=0)
    sem = INDEX.M @ (v / max(np.linalg.norm(v), 1e-9))
    semz = (sem - sem.mean()) / (sem.std() + 1e-6)
    age = (cut - INDEX.pub) / 86400.0
    return semz + np.array([bm.get(i, 0.0) for i in INDEX.ids]) + 0.7 * np.exp(-np.maximum(age, 0) / 21.0)


def auc(score, y):
    pos, neg = score[y == 1], score[y == 0]
    if not len(pos) or not len(neg):
        return float("nan")
    return float((pos[:, None] > neg[None, :]).mean() + 0.5 * (pos[:, None] == neg[None, :]).mean())


idx = np.array([INDEX.pos[p] for p in test])
rng = np.random.default_rng(0)
res = {}
for name, sc in (("v1 Rocchio", v1_scores()), ("v2", recsys.offline_scores(p, q_topic, bm, cut))):
    s_ = sc[idx]
    a = auc(s_, y)
    boots = [auc(s_[b], y[b]) for b in (rng.integers(0, len(y), len(y)) for _ in range(1000))]
    lo, hi = np.nanpercentile(boots, [2.5, 97.5])
    res[name] = s_
    print(f"{name:11s} AUC {a:.3f}  [95% CI {lo:.3f}–{hi:.3f}]")
d = res["v2"] - res["v1 Rocchio"]
diffs = []
for _ in range(1000):
    b = rng.integers(0, len(y), len(y))
    diffs.append(auc(res["v2"][b], y[b]) - auc(res["v1 Rocchio"][b], y[b]))
lo, hi = np.nanpercentile(diffs, [2.5, 97.5])
print(f"v2 − v1     ΔAUC 95% CI {lo:+.3f} … {hi:+.3f}")
fb = recsys.load_feedback(cut)
print("interests learned before the cut:", [(x["label"], len(x["members"])) for x in recsys.interests(fb)])
