"""Second server instance on port 8799 backed by a throw-away COPY of the database, for UI screenshots.
Never touches the live DB/profile. Usage: sandbox_server.py  (Ctrl+C / kill to stop)."""
import sys as _sys, pathlib as _pl
_sys.path.insert(0, str(_pl.Path(__file__).resolve().parents[1]))   # run from anywhere
import shutil, sqlite3, sys, tempfile
from pathlib import Path
from paperscroll import config
tmp = Path(tempfile.gettempdir()) / "paperscroll-sandbox"; tmp.mkdir(exist_ok=True)
db_copy = tmp / "copy.db"
src = sqlite3.connect(f"file:{config.DB_PATH}?mode=ro", uri=True); dst = sqlite3.connect(db_copy); src.backup(dst); src.close(); dst.close()
config.DB_PATH = db_copy
import os as _os
if _os.environ.get("PS_SANDBOX_CLEAN"):   # demo mode: drop the owner's likes, notes, history from the copy
    _c = sqlite3.connect(db_copy)
    for _t in ("interactions", "events", "seen"):
        _c.execute(f"DELETE FROM {_t}")
    _c.commit(); _c.close()
from paperscroll import rank, db, jobs
jobs.start = lambda: __import__("paperscroll.embed", fromlist=["INDEX"]).INDEX.reload()   # no sync/scheduler in the sandbox
jobs.trigger = lambda *a, **k: False
rank.set_profile("bimanual robot manipulation with diffusion policies and VLA models", "diffusion policy, VLA", None)
import uvicorn
from paperscroll.main import app
from starlette.responses import HTMLResponse
from starlette.routing import Route
# phone-sized frame on the same origin (headless Edge resizes the viewport at capture time, so screenshot this instead)
def _frame(req):
    font = req.query_params.get("font", "16")
    return HTMLResponse('<body style="margin:0;background:#888"><script>localStorage.setItem("ps.font","' + font + '")</script>'
                        '<iframe src="/" style="width:412px;height:892px;border:0;display:block"></iframe></body>')
app.router.routes.insert(0, Route("/__frame", _frame))
uvicorn.run(app, host="127.0.0.1", port=8799, log_level="warning")
