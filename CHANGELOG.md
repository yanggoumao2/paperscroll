# Changelog

PaperScroll is actively maintained; this file lists user-visible changes. Dates are UTC+8.

## Unreleased

- On-demand translation through DeepL (free key is enough, set in Settings → 翻译): 译 on a card translates the
  title and the problem/method/result lines, 译 in close reading translates the abstract sentence by sentence
  (colours kept), and selecting any text offers to translate only the selection. Nothing is translated
  automatically; results are cached per language. 17 target languages.

- Recommender v2 (`server/paperscroll/recsys.py`): dwell time relative to your usual pace, figure / close-reading /
  link / share signals, multiple interests (weighted spherical k-means, item-to-item recall), recall channels for
  topic, session, liked authors and exploration, Thompson-sampling allocation between channels, online-learned
  weights for recency / citations / venue / keywords, near-duplicate filtering. `"recommender": "v1"` in
  `data/config.json` switches back. Settings page shows the learned interests.
- Events carry a client id; resent events are stored once (older versions could record the same view twice).
- `server/dev/rec_eval.py`: offline replay of your own history (read vs skipped, ROC-AUC, v1 vs v2).

- Contribution guide in English and Chinese (fork → pull request, how to get credited), pull request template,
  contributors gallery in the README.

## 0.1.0 — 2026-11-27

First public release.

- Swipeable one-paper-per-screen feed with pull-to-refresh, double-tap to like, reading counter.
- *At a glance*: problem / method / result sentences picked from the abstract by rules (no LLM), numbers highlighted,
  method name and paper type, code and project links, page/figure counts.
- Key figure from arXiv HTML, full-width with top crop for tall figures, full-screen viewer.
- Venue stamp with CCF and CORE levels; citations and published venue from OpenAlex; optional Semantic Scholar TL;DR.
- Ranking: multilingual MiniLM embeddings + BM25 + recency + quality, Rocchio feedback from likes/saves/notes/hides,
  four preference knobs, adjacent-field exploration cards, *why recommended* line.
- Library with notes; export to BibTeX, Markdown, CSV, JSON.
- Daily incremental arXiv sync of configurable categories with a rolling window.
- Paper and night themes, adjustable font size, justified text with TeX-pattern hyphenation.
- Android shell (Capacitor 7) that loads the UI from the server (UI updates without reinstalling), native splash,
  haptics, share sheet, offline page; ignores the system font scale.
- Windows scheduled-task installer, systemd unit, launchd example.
