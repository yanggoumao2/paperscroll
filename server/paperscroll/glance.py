"""'At a glance' structure for a paper, extracted from its title/abstract/comment with rules (no LLM).

Splits the abstract into sentences and picks the one that states the problem, the one that states the
method and the one that states the result, plus the method name, paper type, code/project links and
page/figure counts. Everything is verbatim text from arXiv, so it can never invent claims."""
from __future__ import annotations

import re

_ABBR = re.compile(r"(?:\b(?:e\.g|i\.e|et al|vs|cf|Fig|Eq|Sec|approx|resp|No|etc)\.)$", re.I)
_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9(\"'\[])")

_METHOD = [
    (re.compile(r"^(?:here,?\s+|in this (?:paper|work|study|letter),?\s+|to (?:address|tackle|overcome|bridge|fill|close|this end)[^,]{0,80},\s*)?"
                r"we\s+(?:propose|introduce|present|develop|design|devise|build|formulate|put forward)", re.I), 6),
    (re.compile(r"\b(?:this|our) (?:paper|work|study|letter) (?:proposes|introduces|presents|develops)", re.I), 6),
    (re.compile(r"\bwe (?:propose|introduce|present|develop|design|devise|construct|curate|release|build|formulate)\b", re.I), 5),
    (re.compile(r"\b(?:called|named|dubbed|termed)\b", re.I), 2),
    (re.compile(r"\b(?:our (?:method|approach|framework|model|system|key idea|insight))\b", re.I), 2),
    (re.compile(r"\b(?:we (?:show|study|investigate|explore|analy[sz]e|leverage|train|use|adopt|frame|cast|treat|reformulate))\b", re.I), 1),
]
_RESULT = [
    (re.compile(r"\b(?:outperform\w*|surpass\w*|beat\w*|exceed\w*)\b", re.I), 4),
    (re.compile(r"\bstate[- ]of[- ]the[- ]art\b|\bSOTA\b", re.I), 3),
    (re.compile(r"\d+(?:\.\d+)?\s?(?:%|×|x\b|-fold|\s?fold\b|\s?percentage points|\s?pp\b)", re.I), 3),
    (re.compile(r"\b(?:achiev\w*|improv\w*|reduc\w*|boost\w*|gain\w*|speed[- ]?up\w*|faster|accelerat\w*|success rate)\b", re.I), 2),
    (re.compile(r"\b(?:experiments?|results?|evaluations?|empirical\w*)\b.{0,40}\b(?:show|demonstrate|reveal|indicate|confirm|suggest)", re.I), 3),
    (re.compile(r"\b(?:we (?:show|demonstrate|find|observe)|extensive)\b", re.I), 1),
]
_PROBLEM = [
    (re.compile(r"\b(?:however|yet|but|nevertheless|despite|although|while)\b", re.I), 3),
    (re.compile(r"\b(?:remains?|still)\b.{0,40}\b(?:challeng\w*|open|unclear|difficult|limited|unsolved|elusive)", re.I), 4),
    (re.compile(r"\b(?:challeng\w*|limitation\w*|limited|struggle\w*|fail\w*|lack\w*|costly|expensive|bottleneck\w*|"
                r"suffer\w*|hinder\w*|insufficient|unexplored|underexplored|overlooked|prohibitive|brittle|scarce)\b", re.I), 2),
    (re.compile(r"\b(?:is (?:crucial|critical|essential|important|key)|plays? a (?:key|crucial|central) role)\b", re.I), 1),
]
_AVAIL = re.compile(r"\b(?:code|data|dataset|models?|weights|checkpoints|project page|videos?)\b.{0,60}\b(?:available|released?|open[- ]?sourced?|at https?)|\bavailable at\b", re.I)
_URL = re.compile(r"https?://[^\s<>\"'\)\]\},;]+")
_CODE_HOSTS = ("github.com", "gitlab.com", "huggingface.co", "bitbucket.org", "codeberg.org")


def clean(text: str) -> str:
    """Strip the LaTeX that arXiv authors leave in abstracts."""
    t = re.sub(r"\\(?:textbf|textit|emph|texttt|mathrm|mathbf|text|textsc|mathcal)\{([^{}]*)\}", r"\1", text or "")
    t = re.sub(r"\\([%&_#])", r"\1", t)
    t = re.sub(r"\$([^$]{1,60})\$", lambda m: re.sub(r"[{}\\]|_|\^", "", m.group(1)), t)
    t = t.replace("---", "—").replace("--", "–").replace("~", " ").replace("``", "\u201c").replace("''", "\u201d")
    return t


def sentences(text: str) -> list[str]:
    text = re.sub(r"\s+", " ", clean(text).strip())
    out: list[str] = []
    for part in _SPLIT.split(text):
        if out and (_ABBR.search(out[-1]) or len(out[-1]) < 25):
            out[-1] = out[-1] + " " + part
        else:
            out.append(part)
    return [s for s in out if s]


def _score(s: str, rules) -> int:
    return sum(w for rx, w in rules if rx.search(s))


def _tidy(s: str) -> str:
    s = re.sub(r"^(?:however|moreover|furthermore|additionally|in addition|notably|specifically|importantly|finally),\s*", "", s, flags=re.I)
    s = re.sub(r"^(?:here,?\s+|in this (?:paper|work|study|letter),?\s+)", "", s, flags=re.I)
    return s[:1].upper() + s[1:] if s else s


def _name(title: str, method: str) -> str:
    m = re.match(r"^\s*([^:]{2,40}?)\s*:\s+\S", title or "")
    if m and len(m.group(1).split()) <= 4 and not re.search(r"\b(?:towards?|on|how|why|when|what|beyond|rethinking)\b", m.group(1), re.I):
        cand = m.group(1).strip()
        # a one-token prefix (CRISP, FoveaVLA) is a name; a multi-word one only if the abstract uses it as one
        if " " not in cand or cand.lower() in (method or "").lower():
            return cand
    m = re.search(r"\b(?:called|named|dubbed|termed)\s+([A-Z][\w\-+.²³]*[A-Za-z0-9+])", method or "")
    if m:
        return m.group(1)
    m = re.search(r"\b(?:propose|introduce|present)s?\s+([A-Z][a-z]*[A-Z][\w\-+]*|[A-Z]{2,}[\w\-+]*)\b", method or "")
    return m.group(1) if m else ""


def _kinds(title: str, abstract: str) -> list[str]:
    t, a = (title or "").lower(), (abstract or "").lower()
    k = []
    if re.search(r"\b(survey|review|overview|tutorial|primer)\b", t):
        k.append("综述")
    if re.search(r"\bbenchmark", t) or re.search(r"\bwe (?:introduce|present|propose|release) (?:a |an )?(?:new )?[\w\- ]{0,30}benchmark", a):
        k.append("基准")
    if re.search(r"\bdataset\b", t) or re.search(r"\bwe (?:introduce|present|release|collect|curate) (?:a |an )?(?:new )?[\w\- ]{0,30}dataset", a):
        k.append("数据集")
    if re.search(r"\bposition\b", t) or a.startswith("this position paper"):
        k.append("观点")
    if re.search(r"\bwe (?:prove|derive|establish)\b|\btheorem\b|\bregret bound|\bconvergence rate", a):
        k.append("理论")
    if re.search(r"\breal[- ]world (?:robot|experiment|deployment)|\bphysical robot|\breal robot", a):
        k.append("真机")
    return k


def analyze(title: str, abstract: str, comment: str | None = None) -> dict:
    sents = sentences(abstract)
    n = len(sents)
    roles: dict[str, int] = {}
    if n:
        ms = [_score(s, _METHOD) for s in sents]
        mi = max(range(n), key=lambda i: (ms[i], -i)) if max(ms) > 0 else min(1, n - 1)
        roles["method"] = mi
        if mi > 0:
            ps = [_score(s, _PROBLEM) + (1 if i == mi - 1 else 0) for i, s in enumerate(sents[:mi])]
            roles["problem"] = max(range(mi), key=lambda i: (ps[i], i))
        after = list(range(mi + 1, n))
        if after:
            rs = {i: _score(sents[i], _RESULT) + (i - mi) * 0.1 - (20 if _AVAIL.search(sents[i]) else 0) for i in after}
            best = max(after, key=lambda i: rs[i])
            if rs[best] >= 2:
                roles["result"] = best
            else:
                tail = [i for i in after if not _AVAIL.search(sents[i])]
                if tail:
                    roles["result"] = tail[-1]
        elif n >= 2 and "problem" not in roles:
            roles["result"] = n - 1
    blob = f"{abstract or ''} {comment or ''}"
    code_soon = bool(re.search(r"\b(?:code|models?|data)\b.{0,40}\b(?:will be|to be)\b.{0,30}\b(?:released|available|open)", blob, re.I))
    code, project = [], []
    for u in _URL.findall(blob):
        u = u.rstrip(".")
        if u in code or u in project:
            continue
        (code if any(h in u for h in _CODE_HOSTS) else project).append(u)
    pages = re.search(r"(\d+)\s*pages", comment or "", re.I)
    figs = re.search(r"(\d+)\s*figures", comment or "", re.I)
    method = sents[roles["method"]] if "method" in roles else ""
    return {
        "title": clean(title),
        "problem": _tidy(sents[roles["problem"]]) if "problem" in roles else "",
        "method": _tidy(method),
        "result": _tidy(sents[roles["result"]]) if "result" in roles else "",
        "roles": {k: v for k, v in roles.items()},   # sentence indices, for colouring the full abstract
        "sents": sents,
        "name": _name(title, method),
        "kinds": _kinds(title, abstract),
        "code": code[:2],
        "project": project[:2],
        "code_soon": code_soon and not code,
        "pages": int(pages.group(1)) if pages else None,
        "figures": int(figs.group(1)) if figs else None,
    }
