# Changelog

PaperScroll is actively maintained; this file lists user-visible changes. Dates are UTC+8.

## Unreleased

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
