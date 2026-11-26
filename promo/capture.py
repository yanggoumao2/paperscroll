"""Capture real PaperScroll screens from the sandbox server (dev/sandbox_server.py on :8799, a COPY of the DB).

Never talks to the live server. Output: promo/shots/*.png at 412x892 CSS px, device scale 2.5.
"""
import asyncio
from pathlib import Path

from playwright.async_api import async_playwright

BASE = "http://127.0.0.1:8799"
OUT = Path(__file__).with_name("shots"); OUT.mkdir(exist_ok=True)
VIEW = {"width": 412, "height": 892}
INIT = "try{localStorage.setItem('ps.hinted','true');localStorage.setItem('ps.font','16')}catch(e){}"


async def ready(page, ms=2500):
    await page.wait_for_selector(".card:not(.skeleton)", timeout=90000)
    await page.wait_for_load_state("networkidle")
    await page.wait_for_timeout(ms)


async def card_shot(page, idx, name):
    h = await page.evaluate("document.querySelector('#feed').clientHeight")
    await page.evaluate(f"document.querySelector('#feed').scrollTo(0, {idx} * {h})")
    await page.wait_for_timeout(1400)
    await page.screenshot(path=str(OUT / f"{name}.png"))


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(channel="msedge", headless=True)

        async def ctx(dark=False):
            c = await browser.new_context(viewport=VIEW, device_scale_factor=2.5, color_scheme="dark" if dark else "light",
                                          locale="zh-CN", is_mobile=True, has_touch=True)
            await c.add_init_script(INIT)
            return c

        # 1) a feed: five consecutive cards
        c = await ctx(); page = await c.new_page()
        await page.goto(BASE + "/"); await ready(page, 4000)
        for i in range(5):
            await card_shot(page, i, f"feed_{i}")
        # close-reading sheet of card 0
        await card_shot(page, 0, "feed_0b")
        await page.click(".card >> nth=0 >> .actions [data-act=detail]")
        await page.wait_for_timeout(1200)
        await page.screenshot(path=str(OUT / "sheet.png"))
        await page.mouse.click(206, 60); await page.wait_for_timeout(600)
        # like + save a few cards (sandbox copy only), then the library
        for i in range(3):
            await page.click(f".card >> nth={i} >> .actions [data-act=like]")
            await page.wait_for_timeout(300)
        await page.click(".card >> nth=1 >> .actions [data-act=save]")
        await page.wait_for_timeout(1500)
        await page.click(".tabbar [data-view=library]"); await page.wait_for_timeout(2500)
        await page.screenshot(path=str(OUT / "library.png"))
        await page.click(".tabbar [data-view=settings]"); await page.wait_for_timeout(2500)
        await page.screenshot(path=str(OUT / "settings.png"))
        await c.close()

        # 2) pinned showcase cards (venue stamp + levels, code link)
        for pid, name, dark in [("2611.27101", "card_venue", False), ("2611.30787", "card_venue2", False),
                                ("2611.22506", "card_cvpr", False), ("2611.30787", "card_night", True)]:
            c = await ctx(dark); page = await c.new_page()
            await page.goto(f"{BASE}/?p={pid}"); await ready(page, 4000)
            await page.screenshot(path=str(OUT / f"{name}.png"))
            await c.close()
        await browser.close()
    print("captured:", sorted(x.name for x in OUT.glob("*.png")))


asyncio.run(main())
