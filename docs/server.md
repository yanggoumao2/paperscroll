# Server setup

The server is a single Python process: it ingests arXiv, computes embeddings, ranks papers and serves both
the JSON API and the web interface. It runs on Windows 10/11, Linux and macOS.

- [Requirements](#requirements)
- [Install](#install)
- [Run it in the background](#run-it-in-the-background)
- [Reach it from your phone](#reach-it-from-your-phone)
- [Security](#security)
- [Updating](#updating)
- [Uninstall](#uninstall)

## Requirements

| | Minimum | Notes |
|---|---|---|
| Python | 3.11 or 3.12 | installed and managed by [uv](https://docs.astral.sh/uv/getting-started/installation/) |
| RAM | 1 GB free | ~50 MB resident when idle; the embedding model is loaded on demand |
| Disk | ~1 GB | model 240 MB, database ~260 MB for 50k papers, figure cache, virtualenv ~150 MB |
| Network | outbound HTTPS | `export.arxiv.org`, `arxiv.org`, `api.openalex.org`, optionally `api.semanticscholar.org`, and Hugging Face once for the model |
| Uptime | the machine should stay on | sync runs at 12:35 and 23:30 local time and catches up on start if it missed one |

No GPU is needed.

## Install

```bash
git clone https://github.com/yanggoumao2/paperscroll.git
cd paperscroll/server
uv sync
uv run python run.py
```

Open <http://127.0.0.1:8765>. On first start PaperScroll

1. downloads the embedding model (`paraphrase-multilingual-MiniLM-L12-v2`, ONNX, ~240 MB) into `data/models/`;
2. backfills the configured window (default: 90 days of 9 categories, ~50k papers) from the arXiv API in
   7-day slices, politely spaced (arXiv asks for ≥3 s between requests);
3. embeds every paper on the CPU (~50–60 papers/s on a laptop) and builds the search index;
4. starts looking up citations and venues on OpenAlex in the background.

You can start using the feed while this runs; *Settings → Library* shows progress. Write your research
topic in **English** — the papers are in English and cross-lingual matching is noticeably weaker.

> **Mainland China:** arXiv and OpenAlex are usually reachable directly. Hugging Face (model download) may need
> a proxy the first time; set `HTTPS_PROXY` before `uv run`, or copy `data/models/` from another machine.

## Run it in the background

### Windows

```powershell
cd paperscroll\server
uv sync
powershell -ExecutionPolicy Bypass -File scripts\install-windows-task.ps1
```

This registers a scheduled task **PaperScroll Server** that starts `pythonw run.py` at logon without a console
window and restarts it (up to 5 times, 1 minute apart) if it crashes. Logs go to `data\paperscroll.log` and
`data\server-console.log`.

Manage it with `Start-ScheduledTask` / `Stop-ScheduledTask -TaskName 'PaperScroll Server'`, or remove it with
`Unregister-ScheduledTask -TaskName 'PaperScroll Server' -Confirm:$false`.

To keep the PC from sleeping, set *Settings → System → Power → Sleep* to *Never* while plugged in.

### Linux (systemd)

```bash
mkdir -p ~/.config/systemd/user
cp server/scripts/paperscroll.service ~/.config/systemd/user/
# edit WorkingDirectory / ExecStart if the repository is not at ~/paperscroll
systemctl --user daemon-reload
systemctl --user enable --now paperscroll
loginctl enable-linger "$USER"        # keep running after you log out
journalctl --user -u paperscroll -f   # follow logs
```

### macOS (launchd)

Save as `~/Library/LaunchAgents/org.paperscroll.server.plist` (adjust the two paths):

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>org.paperscroll.server</string>
  <key>WorkingDirectory</key><string>/Users/YOU/paperscroll/server</string>
  <key>ProgramArguments</key><array>
    <string>/Users/YOU/paperscroll/server/.venv/bin/python</string><string>run.py</string>
  </array>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
</dict></plist>
```

Then `launchctl load ~/Library/LaunchAgents/org.paperscroll.server.plist`.

## Reach it from your phone

The server listens on `127.0.0.1:8765` only. The recommended way to reach it from a phone is
[Tailscale](https://tailscale.com) (free for personal use): a private, encrypted network between your own
devices that works across Wi-Fi, mobile data and NAT, with nothing exposed to the internet.

1. Install Tailscale on the computer and on the phone, and sign in to the same account on both.
   Android without Google Play: download the APK from Tailscale's
   package page (<https://pkgs.tailscale.com/stable/>, "Android" section).
2. On the computer, publish the server to your tailnet only:

   ```bash
   # reachable by IP:      http://<computer-tailscale-ip>:8766   (recommended for the app)
   tailscale serve --bg --tcp=8766 tcp://127.0.0.1:8765
   # reachable by name:    http://<computer-name>.<tailnet>.ts.net:8765
   tailscale serve --bg --http=8765 http://127.0.0.1:8765
   ```

   `tailscale ip -4` prints the computer's Tailscale IP (`100.x.y.z`). The settings survive reboots.
   Check with `tailscale serve status`; undo with `tailscale serve reset`.
3. On the phone (Tailscale connected), open `http://100.x.y.z:8766` in the browser — you should see the feed.
   Then [build the app](android.md) with that address, or use *Add to home screen* in the browser.

**If the phone cannot connect**
- Make sure Tailscale on the phone says *Connected*. Some Android skins (Huawei, Xiaomi, OPPO…) kill VPN apps in
  the background: allow Tailscale to run in the background and exclude it from battery optimisation.
- `tailscale ping <phone-name>` on the computer should say `via <ip:port>` (direct). `via DERP(...)` means the
  traffic is relayed and will be slow. A proxy running in TUN / "enhanced" mode on the computer (Clash, V2Ray…)
  often causes this: exclude `100.64.0.0/10` (and your LAN) from the TUN, or add a
  `PROCESS-NAME,tailscaled(.exe),DIRECT` rule.

**Without Tailscale**: you can set `"host": "0.0.0.0"` in `data/config.json` and use the computer's LAN IP while
on the same Wi-Fi, but read [Security](#security) first. ZeroTier, WireGuard or any VPN you control work the same way.

## Security

PaperScroll has **no login**. Anyone who can reach the port can read your library and change your settings.

- Keep the default `"host": "127.0.0.1"` and publish through Tailscale (`tailscale serve` is tailnet-only).
- Do not port-forward it on your router and do not use `tailscale funnel`.
- If you bind to `0.0.0.0`, do it only on a network you trust and consider a firewall rule limiting the source.
- API keys are stored in plain text in `data/config.json`; the `data/` directory is git-ignored — keep it that way.

## Updating

```bash
cd paperscroll
git pull
cd server && uv sync
# restart: Windows   Stop-ScheduledTask / Start-ScheduledTask -TaskName 'PaperScroll Server'
#          Linux     systemctl --user restart paperscroll
```

Interface changes (`web/`) are picked up by the phone app on its next start — it shows a *「界面有更新」(UI updated)* banner if it is open. Database migrations run automatically on start. Re-build the APK only when the release
notes say so.

## Uninstall

1. Stop and remove the background service (see above).
2. `tailscale serve reset`
3. Delete the repository folder (this also deletes `data/`, i.e. your library — export it first).
