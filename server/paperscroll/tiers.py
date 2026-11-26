"""Venue level lookup: CCF recommended list (A/B/C) and CORE/ICORE conference rank (A*/A/B/C).

Data is venue_tiers.json, built by tools/build_tiers.py from the official lists. Venues that neither
list ranks (e.g. CoRL, RSS, RA-L, TMLR) return no tier rather than a guess."""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

_DATA = json.loads((Path(__file__).with_name("venue_tiers.json")).read_text(encoding="utf-8"))
_norm = lambda s: re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()
_key = lambda s: re.sub(r"[\s\-]+", "", (s or "").upper())

# our short labels -> keys used by the lists
_ALIAS = {"NIPS": "NEURIPS", "MM": "ACMMM", "ACMMM": "ACMMM", "TPAMI": "TPAMI"}
_ALIAS_FULL = {"TRO": "ieee transactions on robotics"}
# long OpenAlex source names -> short labels (checked as substrings of the normalised name)
_SHORT = [
    ("neural information processing systems", "NeurIPS"), ("international conference on machine learning", "ICML"),
    ("learning representations", "ICLR"), ("computer vision and pattern recognition", "CVPR"),
    ("international conference on computer vision", "ICCV"), ("european conference on computer vision", "ECCV"),
    ("aaai conference on artificial intelligence", "AAAI"), ("international joint conference on artificial intelligence", "IJCAI"),
    ("robotics and automation letters", "RA-L"), ("transactions on robotics", "T-RO"),
    ("international conference on robotics and automation", "ICRA"), ("intelligent robots and systems", "IROS"),
    ("conference on robot learning", "CoRL"), ("robotics science and systems", "RSS"),
    ("international journal of robotics research", "IJRR"), ("pattern analysis and machine intelligence", "TPAMI"),
    ("international journal of computer vision", "IJCV"), ("transactions on image processing", "TIP"),
    ("empirical methods in natural language processing", "EMNLP"), ("association for computational linguistics", "ACL"),
    ("transactions on machine learning research", "TMLR"), ("journal of machine learning research", "JMLR"),
    ("knowledge discovery and data mining", "KDD"), ("acm multimedia", "ACM MM"), ("transactions on graphics", "TOG"),
    ("winter conference on applications of computer vision", "WACV"), ("acoustics speech and signal processing", "ICASSP"),
]


@lru_cache(maxsize=4096)
def lookup(venue: str) -> dict:
    """venue: a short label like 'CVPR 2026' or a long source name. Returns {short, ccf, core} (values may be '')."""
    if not venue:
        return {"short": "", "ccf": "", "core": ""}
    name = re.sub(r"\b(?:19|20)\d\d\b", "", venue).strip()
    n = _norm(name)
    short = name
    fm = re.search(r"findings of (?:the association for computational linguistics\W*)?(acl|emnlp|naacl|eacl)", n)
    if fm:   # Findings tracks are not ranked by CCF or CORE
        return {"short": "Findings of " + fm.group(1).upper(), "ccf": "", "core": ""}
    for pat, lab in _SHORT:
        if pat in n:
            short = lab
            break
    k = _key(short)
    k = _ALIAS.get(k, k)
    ccf = _DATA["ccf_abbr"].get(k, "")
    core = _DATA["core_abbr"].get(k, "")
    full = _ALIAS_FULL.get(k)
    if full:
        ccf = ccf or _DATA["ccf_full"].get(full, "")
    if not (ccf or core) and len(n) > 12:   # long name not in our short list: exact full-name match only
        ccf = _DATA["ccf_full"].get(n, "")
        core = _DATA["core_full"].get(n, "")
    return {"short": short if len(short) <= 24 else "", "ccf": ccf, "core": core}
