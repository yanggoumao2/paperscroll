"""Key figure + affiliations from arXiv's official HTML version, and a resized local image cache."""
from __future__ import annotations

import asyncio
import io
import json
import logging
import re
from html.parser import HTMLParser
from urllib.parse import urljoin

import httpx

from . import config, db

log = logging.getLogger("paperscroll.fig")
UA = "paperscroll/0.1 (personal paper reader)"


class _Parser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack: list[tuple[str, str]] = []
        self.fig_depth = None
        self.fig_img = None
        self.first_img = None
        self.aff_depth = None
        self.affs: list[str] = []
        self._buf: list[str] = []
        self.done = False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        cls = a.get("class") or ""
        self.stack.append((tag, cls))
        depth = len(self.stack)
        if tag == "figure" and "ltx_figure" in cls and "ltx_table" not in cls and self.fig_img is None:
            self.fig_depth = depth
        if tag == "img" and a.get("src"):
            if self.fig_depth is not None and self.fig_img is None:
                self.fig_img = a["src"]
            if self.first_img is None and "ltx_graphics" in cls:
                self.first_img = a["src"]
        if self.aff_depth is None and ("ltx_role_affiliation" in cls or "ltx_role_address" in cls):
            self.aff_depth = depth
            self._buf = []
        if tag in ("br",) and self.aff_depth is not None:
            self._buf.append("\n")
        if tag == "img":
            self.stack.pop()   # void element

    def handle_endtag(self, tag):
        if not self.stack:
            return
        # pop to the matching tag (HTML may be sloppy)
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                depth = i + 1
                if self.aff_depth is not None and depth <= self.aff_depth:
                    txt = "".join(self._buf)
                    txt = re.sub(r"Affiliation:\s*", "\n", txt.replace("\xa0", " "))
                    txt = re.sub(r"[*†‡§¶∗]\s*(Equal|Corresponding|Project|Work done)[^\n]*", "", txt, flags=re.I)
                    for part in re.split(r"\n|;", txt):
                        part = re.sub(r"^[\s\d*†‡§¶,∗♠♣♡♢♮\[\]()]+", "", part).strip(" ,[]")
                        if 3 < len(part) < 160 and "@" not in part and not re.search(r"[{}\\]", part) and len(re.findall(r"[A-Za-z\u4e00-\u9fff]", part)) >= 4:
                            self.affs.append(part)
                    self.aff_depth = None
                if self.fig_depth is not None and depth <= self.fig_depth:
                    self.fig_depth = None
                del self.stack[i:]
                return

    def handle_data(self, data):
        if self.aff_depth is not None:
            self._buf.append(data)


def parse_html(html: str, base: str) -> tuple[str | None, list[str]]:
    p = _Parser()
    try:
        p.feed(html[:3_000_000])
    except Exception:
        pass
    src = p.fig_img or p.first_img
    url = urljoin(base, src) if src else None
    affs, seen = [], set()
    for a in p.affs:
        k = a.lower()
        if k not in seen:
            seen.add(k)
            affs.append(a)
    return url, affs[:6]


async def fetch_one(client: httpx.AsyncClient, pid: str) -> None:
    state, fig, affs = 3, None, []
    try:
        r = await client.get(f"https://arxiv.org/html/{pid}", timeout=12)
        if r.status_code == 200 and "ltx_document" in r.text[:200000]:
            fig, affs = parse_html(r.text, str(r.url))
            state = 1 if fig else 2
        elif r.status_code in (404, 200):
            state = 2
    except Exception as ex:
        log.info("html fetch failed %s: %r", pid, ex)
    with db.writer() as w:
        w.execute("UPDATE papers SET fig_state=?, fig_url=?, affiliations=? WHERE id=?",
                  (state, fig, json.dumps(affs, ensure_ascii=False) if affs else None, pid))


async def ensure(pids: list[str]) -> None:
    """Fetch figure/affiliations for papers not yet checked (or errored), in parallel."""
    if not pids:
        return
    con = db.connect()
    q = ",".join("?" * len(pids))
    todo = [r["id"] for r in con.execute(f"SELECT id FROM papers WHERE id IN ({q}) AND fig_state IN (0,3)", pids)]
    con.close()
    if not todo:
        return
    async with httpx.AsyncClient(headers={"User-Agent": UA}, follow_redirects=True) as client:
        await asyncio.gather(*(fetch_one(client, p) for p in todo))


def _safe(pid: str) -> str:
    return re.sub(r"[^0-9A-Za-z._-]", "_", pid)


async def image_bytes(pid: str) -> bytes | None:
    """Return a phone-sized JPEG of the key figure, cached on disk."""
    config.FIG_DIR.mkdir(parents=True, exist_ok=True)
    path = config.FIG_DIR / f"{_safe(pid)}.jpg"
    if path.exists():
        return path.read_bytes()
    con = db.connect()
    row = con.execute("SELECT fig_url FROM papers WHERE id=?", (pid,)).fetchone()
    con.close()
    if not row or not row["fig_url"]:
        return None
    async with httpx.AsyncClient(headers={"User-Agent": UA}, follow_redirects=True) as client:
        try:
            r = await client.get(row["fig_url"], timeout=20)
            r.raise_for_status()
        except Exception:
            return None
    data = r.content
    try:
        from PIL import Image
        im = Image.open(io.BytesIO(data))
        if im.mode in ("RGBA", "LA", "P"):
            im = im.convert("RGBA")
            bg = Image.new("RGB", im.size, (255, 255, 255))
            bg.paste(im, mask=im.split()[-1])
            im = bg
        else:
            im = im.convert("RGB")
        im.thumbnail((1280, 1280))
        out = io.BytesIO()
        im.save(out, "JPEG", quality=82, optimize=True)
        data = out.getvalue()
    except Exception:
        # SVG or unreadable: give up rather than cache junk
        return None
    path.write_bytes(data)
    return data
