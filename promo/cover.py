"""Render cover.html to out/cover.png (video first frame) and out/cover-play.png (README poster)."""
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright
D = Path(__file__).parent; (D / "out").mkdir(exist_ok=True)

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(channel="msedge", headless=True, args=["--allow-file-access-from-files"])
        page = await b.new_page(viewport={"width": 1920, "height": 1080})
        for q, name in (("", "cover.png"), ("?play=1", "cover-play.png")):
            await page.goto((D / "cover.html").as_uri() + q)
            await page.evaluate("document.fonts.ready"); await page.wait_for_timeout(600)
            await page.screenshot(path=str(D / "out" / name))
        await b.close()
    print("ok")

asyncio.run(main())
