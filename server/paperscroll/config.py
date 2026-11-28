"""Paths and the editable config file (data/config.json)."""
from __future__ import annotations

import json
import os
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]          # repository root
DATA = Path(os.environ.get("PAPERSCROLL_DATA") or ROOT / "data")   # database, figures, model, config, logs
WEB = ROOT / "web"
DB_PATH = DATA / "paperscroll.db"
FIG_DIR = DATA / "figs"
MODEL_DIR = DATA / "models"
LOG_PATH = DATA / "paperscroll.log"
CONFIG_PATH = DATA / "config.json"

EMBED_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

DEFAULT_CATEGORIES = ["cs.AI", "cs.LG", "cs.CV", "cs.CL", "cs.RO", "cs.IR", "cs.SD", "eess.AS", "eess.IV"]

DEFAULTS = {
    "categories": DEFAULT_CATEGORIES,
    "window_days": 90,
    "s2_api_key": "",
    "openalex_api_key": "",
    "deepl_api_key": "",
    "translate_lang": "ZH-HANS",
    "sync_times": ["12:35", "23:30"],
    "host": "127.0.0.1",
    "port": 8765,
    "recommender": "v2",     # "v1" = the original Rocchio ranking
}

_lock = threading.Lock()


def load() -> dict:
    DATA.mkdir(parents=True, exist_ok=True)
    cfg = dict(DEFAULTS)
    if CONFIG_PATH.exists():
        try:
            cfg.update(json.loads(CONFIG_PATH.read_text(encoding="utf-8")))
        except Exception:
            pass
    else:
        save(cfg)
    return cfg


def save(cfg: dict) -> None:
    with _lock:
        DATA.mkdir(parents=True, exist_ok=True)
        tmp = CONFIG_PATH.with_suffix(".tmp")
        tmp.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(CONFIG_PATH)
