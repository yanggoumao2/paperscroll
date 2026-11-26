"""Read-only: 160 recent real arXiv titles for the opening 'wall of papers' (from the local DB)."""
import json, sqlite3, sys
from pathlib import Path
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
from paperscroll import config
c = sqlite3.connect(f"file:{config.DB_PATH}?mode=ro", uri=True)
rows = [r[0] for r in c.execute("SELECT title FROM papers ORDER BY published DESC LIMIT 400")]
rows = [t for t in rows if 30 < len(t) < 95][:160]
Path(__file__).with_name("titles.json").write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
print(len(rows))
