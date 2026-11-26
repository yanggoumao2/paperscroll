"""Build paperscroll/venue_tiers.json from the CCF list (via CCFrank4dblp data files, MIT) and the CORE/ICORE export.
Inputs live in data/tiers/ (downloaded once); rerun this when the lists are updated."""
import csv, json, re, sys
from pathlib import Path
T = Path(__file__).resolve().parents[2] / "data" / "tiers"
OUT = Path(__file__).resolve().parents[1] / "paperscroll" / "venue_tiers.json"

def jsobj(name):
    txt = (T / f"{name}.js").read_text(encoding="utf-8")
    return dict(re.findall(r'"([^"]+)":\s*"([^"]*)"', txt[txt.index("{"):]))

rank, abbr, full = jsobj("ccfRankUrl"), jsobj("ccfRankAbbr"), jsobj("ccfRankFull")
norm = lambda s: re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()
ccf_abbr, ccf_full = {}, {}
for url, r in rank.items():
    if r not in ("A", "B", "C"):
        continue
    kind = "journal" if url.startswith("/journals/") else "conf"
    if abbr.get(url):
        ccf_abbr.setdefault(abbr[url].upper().replace("-", "").replace(" ", ""), r)
    if full.get(url):
        ccf_full[norm(full[url])] = r
core_abbr, core_full = {}, {}
with open(T / "core.csv", encoding="utf-8", errors="replace") as f:
    for row in csv.reader(f):
        if len(row) < 5 or row[4] not in ("A*", "A", "B", "C"):
            continue
        core_abbr.setdefault(row[2].upper().replace("-", "").replace(" ", ""), row[4])
        core_full[norm(re.sub(r"\(.*?\)", "", row[1]))] = row[4]
data = {"ccf_abbr": ccf_abbr, "ccf_full": ccf_full, "core_abbr": core_abbr, "core_full": core_full,
        "sources": "CCF 推荐目录 (CCFrank4dblp data, updated 2026-04-06); CORE/ICORE conference ranks export"}
OUT.write_text(json.dumps(data, ensure_ascii=False, indent=0), encoding="utf-8")
print(len(ccf_abbr), len(ccf_full), len(core_abbr), len(core_full))
for k in ["NEURIPS", "NIPS", "CVPR", "ICLR", "ICRA", "IROS", "TRO", "RAL", "IJRR", "CORL", "RSS", "TPAMI", "ACMMM", "MM", "EMNLP", "AAAI", "TMLR", "HUMANOIDS", "CASE", "ICASSP", "INTERSPEECH"]:
    print(k, ccf_abbr.get(k), core_abbr.get(k))
