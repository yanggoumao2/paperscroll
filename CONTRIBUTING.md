# Contributing

[中文版](CONTRIBUTING.zh-CN.md)

Thanks for helping! PaperScroll is a small project; the bar for contributions is "makes reading papers better
for someone and does not make the code harder to run". Everyone is welcome to improve it — fix a bug, propose a
better design, add a paper source, improve the docs — and every merged pull request makes you a contributor.

## How to contribute

1. **Have an idea or a better approach?** For anything bigger than a small fix, open an
   [issue](https://github.com/yanggoumao2/paperscroll/issues/new/choose) first and describe the problem and your
   proposal, so we can agree on the direction before you spend time on it.
2. **Fork** the repository (button at the top right on GitHub) and clone your fork.
3. Create a branch: `git checkout -b fix-figure-crop`.
4. Make the change and test it (see *Development setup* below).
5. Commit, push to your fork and open a **pull request** against `main`. The template will ask what changed and
   how you tested it.
6. The maintainer reviews it; after a round of comments if needed, it is merged.

You do not need write access to the repository — forks and pull requests are the normal way to contribute.

## Getting credit

Merged commits keep you as their author, so you appear in the repository's **Contributors** list and in the
contributors gallery in the README. For that GitHub has to recognise your commit email:

- use an email address that is verified on your GitHub account, or your private
  `ID+username@users.noreply.github.com` address (GitHub → Settings → Emails);
- check with `git config user.email` before committing.

If a change was written together with someone else, add a `Co-authored-by: Name <email>` line at the end of the
commit message and both of you are credited. Larger contributions are also mentioned in `CHANGELOG.md`.
GitHub updates the Contributors list some time after the merge, so it may take a few hours to show up.

## Good places to start

- Items on the [Roadmap](README.md#roadmap): more paper sources (OpenReview, journals), a figure from the PDF
  when there is no arXiv HTML version, an English interface, an iOS shell.
- Better problem/method/result extraction (`server/paperscroll/glance.py`) — show before/after on
  `server/dev/glance_check.py`.
- Missing or wrong venue levels (`server/tools/build_tiers.py`, `server/paperscroll/tiers.py`).
- Docs and translations.

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
- Never commit `data/`, API keys, your own server address or anything private.

## Contact

Kunyu Yang — kyyang26@m.fudan.edu.cn
