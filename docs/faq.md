# FAQ and troubleshooting

**The app says it cannot reach the computer (连不上电脑).**
Check, in order: the computer is on and the server runs (`http://127.0.0.1:8765` works on the computer);
Tailscale on the phone says *Connected*; `http://<address>/api/status` opens in the phone's browser.
Android skins such as EMUI/HarmonyOS, MIUI or ColorOS often stop VPN apps in the background — allow Tailscale
to run in the background and exempt it from battery optimisation. See
[server.md → Reach it from your phone](server.md#reach-it-from-your-phone).

**Everything is slow; the APK download keeps failing.**
Run `tailscale ping <phone>` on the computer. `via DERP(...)` means relayed traffic. The usual cause is a proxy in
TUN mode on the computer capturing Tailscale's own traffic — exclude `100.64.0.0/10` from the TUN or add a
`PROCESS-NAME,tailscaled(.exe),DIRECT` rule, then check again for a direct connection.

**Recommendations look off-topic.**
Write the topic in English and be specific ("bimanual manipulation with diffusion policies and VLA models",
not "robotics"). Add a few keywords. Like or save a handful of good papers and mark bad ones *not interested*;
the profile adapts immediately. Set *主题贴合 (fit)* to *strict*.

**I have seen everything / the feed is empty.**
Widen the window or the categories, relax *fit*, or use *重置已看 (reset seen)* in Settings.

**Some cards have no figure.**
The figure comes from the arXiv HTML version, which about 5% of papers do not have (or whose LaTeX failed to
convert). A PDF fallback is on the roadmap.

**The problem / method / result sentences are wrong for a paper.**
They are picked by rules, not by a language model, so unusual abstracts can fool them. The *精读 (close reading)*
sheet always shows the full abstract. Examples of misfires are welcome in an issue.

**No citations or venue levels yet.**
Enrichment runs in the background after each sync. Without an OpenAlex key it uses a small shared daily budget
and finishes over a few days; with a free key it takes minutes. Recent preprints genuinely have few citations.
Venues that neither the CCF list nor CORE ranks (CoRL, RSS, RA-L, TMLR, …) show no level by design.

**Text is huge / the layout overflows on my phone.**
Install the latest APK (it ignores the system font scale), then pick a size under *设置 → 阅读 → 字号*.

**Can I use it without the Android app?** Yes — any browser on any device that can reach the server.
On Android/iOS use *Add to home screen*.

**Can several people share one server?** Not yet: there is one profile and one library per server.

**Where is my data, and how do I back it up?** In `data/` next to the code (or `PAPERSCROLL_DATA`).
Back up `paperscroll.db` and `config.json`. *Library → export* gives BibTeX/Markdown/CSV/JSON.

**How much traffic does it use?** The first backfill downloads roughly 100–200 MB from arXiv and ~240 MB
for the model; daily syncs are a few MB plus figures for the papers you actually see.
