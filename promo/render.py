"""Render scene.html frame by frame (Playwright + Edge, deterministic time) into frames/%05d.jpg.
   python render.py              all frames at 30 fps
   python render.py 3.5 14 30    only these times -> preview/t_<sec>.jpg"""
import asyncio, json, sys
from pathlib import Path
from playwright.async_api import async_playwright

D = Path(__file__).parent
FPS = 30


async def main():
    tl = json.loads((D / "timeline.json").read_text(encoding="utf-8"))
    titles = json.loads((D / "titles.json").read_text(encoding="utf-8"))
    preview = [float(x) for x in sys.argv[1:]]
    out = D / ("preview" if preview else "frames"); out.mkdir(exist_ok=True)
    async with async_playwright() as p:
        b = await p.chromium.launch(channel="msedge", headless=True, args=["--allow-file-access-from-files"])
        page = await b.new_page(viewport={"width": 1920, "height": 1080}, device_scale_factor=1)
        await page.goto((D / "scene.html").as_uri())
        await page.evaluate("([tl, ti]) => { window.TL = tl; window.TITLES = ti; window.setupScene(); }", [tl, titles])
        await page.evaluate("document.fonts.ready")
        await page.evaluate("Promise.all([...document.images].map(i => i.complete ? 1 : new Promise(r => { i.onload = i.onerror = r; })))")
        await page.wait_for_timeout(500)
        import os
        lo, hi = float(os.environ.get("FROM", 0)), float(os.environ.get("TO", 1e9))   # re-render a time range only
        times = preview or [i / FPS for i in range(int(tl["total"] * FPS))]
        for n, t in enumerate(times):
            if not preview and not (lo <= t < hi):
                continue
            await page.evaluate(f"window.render({t})")
            name = f"t_{t:05.2f}.jpg" if preview else f"{n:05d}.jpg"
            await page.screenshot(path=str(out / name), type="jpeg", quality=92)
            if not preview and n % 300 == 0:
                print("frame", n, "/", len(times), flush=True)
        await b.close()
    print("done", len(times))


asyncio.run(main())
