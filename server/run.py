"""Start the PaperScroll server: .venv\\Scripts\\python.exe run.py"""
import logging
import logging.handlers
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from paperscroll import config  # noqa: E402

config.DATA.mkdir(parents=True, exist_ok=True)
if sys.stdout is None or sys.stderr is None:   # pythonw (scheduled task) has no console streams
    _out = open(config.DATA / "server-console.log", "a", encoding="utf-8", buffering=1)
    sys.stdout = sys.stdout or _out
    sys.stderr = sys.stderr or _out
os.environ.setdefault("HF_HOME", str(config.DATA / "hf"))
logging.getLogger("httpx").setLevel(logging.WARNING)
handler = logging.handlers.RotatingFileHandler(config.LOG_PATH, maxBytes=2_000_000, backupCount=3, encoding="utf-8")
logging.basicConfig(level=logging.INFO, handlers=[handler, logging.StreamHandler()],
                    format="%(asctime)s %(levelname)s %(name)s: %(message)s")

import uvicorn  # noqa: E402

from paperscroll.main import app  # noqa: E402

if __name__ == "__main__":
    cfg = config.load()
    uvicorn.run(app, host=cfg["host"], port=int(cfg["port"]), log_level="warning")
