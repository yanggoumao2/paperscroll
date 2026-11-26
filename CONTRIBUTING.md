# Contributing

Thanks for helping! PaperScroll is a small project; the bar for contributions is "makes reading papers better
for someone and does not make the code harder to run".

## Reporting bugs

Open an issue with:
- what you did, what you expected, what happened;
- platform (Windows/Linux/macOS, phone model and Android version, browser);
- a screenshot for layout problems, and the last lines of `data/paperscroll.log` for server problems
  (remove API keys and anything private first).

Wrong problem/method/result sentences are useful too: include the arXiv id and which sentence should have been picked.

## Development setup

```bash
cd server
uv sync
uv run python run.py            # http://127.0.0.1:8765
```

The interface in `web/` has no build step — edit and reload the page.

- `server/dev/sandbox_server.py` starts a second server on port 8799 on a **copy** of your database, so you can
  try changes without touching your real library or profile.
- `server/dev/glance_check.py 20` prints the extracted problem/method/result for 20 random papers.
- `server/dev/shots_multi.ps1 -path "__frame"` (Windows) takes phone-sized screenshots of the sandbox.

Please never test against your live profile: scripts that change the topic or mark papers as seen will change
what you are recommended.

## Pull requests

- One topic per PR, with a short description of the user-visible effect (screenshots for UI changes).
- Python: standard library + the existing dependencies where possible; type hints; no new heavy dependencies
  without discussion. JavaScript: plain browser JS, no framework, no build step.
- Keep the server runnable on Windows, Linux and macOS.
- Update `CHANGELOG.md` under *Unreleased* and the docs if behaviour changes.

## Contact

Kunyu Yang — kyyang26@m.fudan.edu.cn
