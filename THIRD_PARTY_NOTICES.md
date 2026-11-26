# Third-party notices

PaperScroll's own code is MIT-licensed (see [LICENSE](LICENSE)). It bundles or uses the following.

## Bundled in this repository

| Component | Where | License |
|---|---|---|
| Crimson Pro (fonts) | `web/fonts/CrimsonPro-*.woff2` | SIL Open Font License 1.1 — © The Crimson Pro Project Authors |
| Atkinson Hyperlegible (fonts) | `web/fonts/AtkinsonHyperlegible-*.woff2` | SIL Open Font License 1.1 — © Braille Institute of America |
| IBM Plex Mono (fonts) | `web/fonts/IBMPlexMono-*.woff2` | SIL Open Font License 1.1 — © IBM Corp. |
| hyphen (JavaScript hyphenation) | `web/vendor/hyphen.js` | ISC — © Yevhen Tiurin, see `web/vendor/hyphen-LICENSE.txt` |
| en-US hyphenation patterns | `web/vendor/hyphen-en-us.js` | distributed with the `hyphen` npm package (ISC); patterns originate from the TeX `hyph-utf8` project (hyph-en-us) |
| Venue level table | `server/paperscroll/venue_tiers.json` | derived from the CCF recommended list via [CCFrank4dblp](https://github.com/WenyanLiu/CCFrank4dblp) data files (MIT) and the [CORE/ICORE](https://portal.core.edu.au/conf-ranks/) conference export; rankings belong to CCF and CORE |

The font files are subsets of the official releases; the full OFL text is at <https://openfontlicense.org>.

## Downloaded or installed at runtime / build time

| Component | License |
|---|---|
| `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` (embedding model, via fastembed) | Apache-2.0 |
| FastAPI, Uvicorn, httpx, NumPy, fastembed (Python dependencies) | MIT / BSD / Apache-2.0 |
| Capacitor and plugins (Android shell) | MIT |
| AndroidX libraries | Apache-2.0 |

## Data sources

- **arXiv** — metadata via the arXiv API, figures from arXiv HTML. Thank you to arXiv for use of its open access
  interoperability. Paper content remains © its authors and is shown under the license chosen for each paper.
- **OpenAlex** — CC0.
- **Semantic Scholar** — used under the Semantic Scholar API License Agreement when a key is configured.
