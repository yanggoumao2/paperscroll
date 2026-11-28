"""Translation of titles and abstract sentences through the DeepL API (free or Pro key in data/config.json).

Only text the reader asks for is sent, sentence by sentence so the close-reading colours still line up, and every
result is cached in the database: a paper is translated into a language at most once."""
from __future__ import annotations

import hashlib
import logging
import time

import httpx

from . import config, db

log = logging.getLogger("paperscroll.translate")

# DeepL target codes → name shown in settings
LANGS = {
    "ZH-HANS": "简体中文", "ZH-HANT": "繁體中文", "JA": "日本語", "KO": "한국어", "EN-US": "English",
    "DE": "Deutsch", "FR": "Français", "ES": "Español", "IT": "Italiano", "PT-BR": "Português (Brasil)",
    "RU": "Русский", "UK": "Українська", "PL": "Polski", "NL": "Nederlands", "TR": "Türkçe",
    "AR": "العربية", "ID": "Bahasa Indonesia",
}
DEFAULT_LANG = "ZH-HANS"

class TranslateError(Exception):
    pass


def _endpoint(key: str) -> str:
    return "https://api-free.deepl.com" if key.endswith(":fx") else "https://api.deepl.com"


def _key() -> str:
    k = (config.load().get("deepl_api_key") or "").strip()
    if not k:
        raise TranslateError("no DeepL API key")
    return k


def _h(lang: str, text: str) -> str:
    return hashlib.sha1(f"{lang}\0{text}".encode("utf-8")).hexdigest()


def translate(texts: list[str], lang: str, source: str | None = "EN") -> list[str]:
    """Translate a list of strings (English by default; source=None lets DeepL detect it, for selected text).
    Cached strings are not sent again."""
    if lang not in LANGS:
        raise TranslateError(f"unsupported language {lang}")
    out: list[str | None] = [None] * len(texts)
    todo: list[int] = []
    con = db.connect()
    for i, t in enumerate(texts):
        if not (t or "").strip():
            out[i] = t
            continue
        r = con.execute("SELECT text FROM translations WHERE h=?", (_h(lang, t),)).fetchone()
        if r:
            out[i] = r[0]
        else:
            todo.append(i)
    con.close()
    if todo:
        key = _key()
        with httpx.Client(timeout=30) as client:
            for s in range(0, len(todo), 50):   # DeepL accepts up to 50 texts per request
                chunk = todo[s:s + 50]
                res = _post(client, key, [texts[i] for i in chunk], lang, source)
                with db.writer() as w:
                    for i, tr in zip(chunk, res):
                        out[i] = tr
                        w.execute("INSERT OR REPLACE INTO translations(h, lang, text, ts) VALUES(?,?,?,?)",
                                  (_h(lang, texts[i]), lang, tr, time.time()))
    return [x if x is not None else "" for x in out]


def _post(client: httpx.Client, key: str, texts: list[str], lang: str, source: str | None) -> list[str]:
    body = {"text": texts, "target_lang": lang, "preserve_formatting": True}
    if source:
        body["source_lang"] = source
    for attempt in range(4):
        r = client.post(_endpoint(key) + "/v2/translate", json=body,
                        headers={"Authorization": f"DeepL-Auth-Key {key}"})
        if r.status_code == 200:
            return [t["text"] for t in r.json()["translations"]]
        if r.status_code in (429, 500, 502, 503, 504) and attempt < 3:
            time.sleep(1.5 * 2 ** attempt)
            continue
        msg = {403: "DeepL key rejected", 456: "DeepL monthly quota used up"}.get(r.status_code, f"DeepL HTTP {r.status_code}")
        raise TranslateError(msg)
    raise TranslateError("DeepL unavailable")


def usage() -> dict | None:
    k = (config.load().get("deepl_api_key") or "").strip()
    if not k:
        return None
    try:
        r = httpx.get(_endpoint(k) + "/v2/usage", headers={"Authorization": f"DeepL-Auth-Key {k}"}, timeout=10)
        r.raise_for_status()
        d = r.json()
        return {"used": d.get("character_count", 0), "limit": d.get("character_limit", 0)}
    except Exception as e:   # usage is informational only
        log.info("DeepL usage failed: %s", e)
        return {"error": str(e)[:80]}
