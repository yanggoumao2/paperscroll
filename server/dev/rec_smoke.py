"""Call the v2 feed a few times on a COPY of the database and print timing, channels and why-lines."""
import sys as _sys, pathlib as _pl
_sys.path.insert(0, str(_pl.Path(__file__).resolve().parents[1]))
import sqlite3, tempfile, time
from pathlib import Path
from paperscroll import config
tmp = Path(tempfile.gettempdir()) / "paperscroll-recsmoke"; tmp.mkdir(exist_ok=True)
copy = tmp / "copy.db"
s = sqlite3.connect(f"file:{config.DB_PATH}?mode=ro", uri=True); d = sqlite3.connect(copy); s.backup(d); s.close(); d.close()
config.DB_PATH = copy
from paperscroll import db, rank, recsys
from paperscroll.embed import INDEX
INDEX.reload()
print("state:", recsys.explain())
con = db.connect()
for b in range(4):
    t = time.time()
    ids, exp, why = rank._feed_v2(6, 90, None)
    dt = time.time() - t
    print(f"batch {b}: {dt:.2f}s  weights {recsys.LAST.get('weights')}")
    for i in ids:
        title = con.execute("SELECT title FROM papers WHERE id=?", (i,)).fetchone()[0]
        print("  ", why.get(i), "|", title[:80])
