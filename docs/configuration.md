# Configuration

## In the app (*设置 / Settings*)

| Section | Setting | Effect |
|---|---|---|
| 我的课题 (Topic) | one-sentence research description | the main query vector; write it in English |
| | keywords (comma-separated) | boost exact matches (BM25) and appear in *why recommended* |
| | 时间 (recency) | newest only · fresher first · don't care |
| | 主题贴合 (fit) | strict · balanced · broad (also controls how many adjacent-field cards appear) |
| | 成色 (quality) | everything · prefer accepted papers (CCF-A / CORE A* count more) · prefer highly cited · classics |
| | 新鲜感 (novelty) | stable · balanced · more surprises (adds randomness to the ranking) |
| 阅读 (Reading) | theme | follow system · paper · night |
| | density | minimal (method only) · standard · full |
| | font size | 14–21 px; the card re-flows to fit |
| 论文库 (Library) | arXiv categories | any arXiv category code, e.g. `cs.RO`, `eess.SY`, `q-bio.NC`; new ones are backfilled |
| | retention window | 30 / 60 / 90 / 180 / 365 days; older papers are pruned unless liked, saved or noted |
| | OpenAlex API key | faster citation/venue enrichment ([get one](https://openalex.org/settings/api)) |
| | Semantic Scholar API key | enables TL;DR summaries ([apply](https://www.semanticscholar.org/product/api)) |
| | 立即同步 / 重置已看 | sync now · forget which papers you have already seen |
| 连接 (Connection) | server address | only in the Android app; switches to another PaperScroll server |

## `data/config.json`

Created on first start. Edit it while the server is stopped, or use the app for the settings above.

```json
{
  "categories": ["cs.AI", "cs.LG", "cs.CV", "cs.CL", "cs.RO", "cs.IR", "cs.SD", "eess.AS", "eess.IV"],
  "window_days": 90,
  "sync_times": ["12:35", "23:30"],
  "host": "127.0.0.1",
  "port": 8765,
  "openalex_api_key": "",
  "s2_api_key": ""
}
```

| Key | Default | Notes |
|---|---|---|
| `categories` | 9 AI-related categories | arXiv category codes |
| `window_days` | `90` | rolling window kept in the database |
| `sync_times` | `["12:35", "23:30"]` | local times for the incremental sync; arXiv publishes new papers once a day (~20:00 US Eastern) |
| `host` | `127.0.0.1` | `0.0.0.0` exposes it on all interfaces — read [Security](server.md#security) first |
| `port` | `8765` | |
| `openalex_api_key` | empty | without a key: ≤400 requests/day on the shared anonymous budget (≈20k papers/day) |
| `s2_api_key` | empty | without a key Semantic Scholar is usually rate-limited and simply skipped |

## Environment variables

| Variable | Effect |
|---|---|
| `PAPERSCROLL_DATA` | put `data/` somewhere else (e.g. a bigger disk) |
| `HTTPS_PROXY` / `HTTP_PROXY` | proxy for arXiv / OpenAlex / model download (honoured by httpx and Hugging Face) |
| `PAPERSCROLL_SERVER` | default server address for `app/build-apk.*` |

## Files in `data/`

| Path | Content |
|---|---|
| `paperscroll.db` | SQLite database: papers, embeddings, full-text index, your interactions, notes, profile |
| `figs/` | cached key figures (JPEG, ≤1280 px) |
| `models/` | the embedding model |
| `config.json` | settings above, including API keys |
| `paperscroll.log`, `server-console.log` | logs (rotated at 2 MB) |

Back up `paperscroll.db` and `config.json` to keep your library; everything else can be re-downloaded.
