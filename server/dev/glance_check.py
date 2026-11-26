"""Read-only check of glance extraction on random papers. Does not touch the live profile or write the DB."""
import sys as _sys, pathlib as _pl
_sys.path.insert(0, str(_pl.Path(__file__).resolve().parents[1]))   # run from anywhere
import random, sqlite3, sys, textwrap
sys.stdout.reconfigure(encoding="utf-8")
from paperscroll import config, glance
con = sqlite3.connect(f"file:{config.DB_PATH}?mode=ro", uri=True); con.row_factory = sqlite3.Row
rows = con.execute("SELECT id,title,abstract,comment FROM papers WHERE primary_cat IN ('cs.RO','cs.CV','cs.LG','cs.CL') ORDER BY random() LIMIT ?", (int(sys.argv[1]) if len(sys.argv) > 1 else 8,)).fetchall()
for r in rows:
    g = glance.analyze(r["title"], r["abstract"], r["comment"])
    print("=" * 90); print(r["id"], "|", r["title"]); print("name:", g["name"], "| kinds:", g["kinds"], "| code:", g["code"], "| proj:", g["project"], "| pages:", g["pages"], g["figures"], "| nsent:", len(g["sents"]), g["roles"])
    for k in ("problem", "method", "result"):
        print(f"  [{k}] " + textwrap.shorten(g[k], 260))
