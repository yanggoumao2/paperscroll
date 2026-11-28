"""Screenshots of on-demand translation in the sandbox (port 8799): card 译, close-reading 译, selection 译.
Run with the promo venv (Playwright + Edge): promo/.venv/Scripts/python server/dev/tr_shots.py OUTDIR"""
import sys, time
from pathlib import Path
from playwright.sync_api import sync_playwright

out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
with sync_playwright() as p:
    b = p.chromium.launch(channel="msedge")
    pg = b.new_page(viewport={"width": 412, "height": 892}, device_scale_factor=2)
    pg.goto("http://127.0.0.1:8799/")
    pg.wait_for_selector(".card:not(.skeleton) h2", timeout=60000)
    time.sleep(2)
    card = pg.locator(".card:not(.skeleton)").first
    pg.screenshot(path=str(out / "1_original.png"))
    card.locator(".tr-btn").click()
    pg.wait_for_selector(".card.translated", timeout=60000)
    time.sleep(1)
    pg.screenshot(path=str(out / "2_card_translated.png"))
    card.locator(".tr-btn").click()      # back to original
    time.sleep(0.5)
    # select part of the method row and translate only that
    pg.evaluate("""() => { const n = document.querySelector('.card:not(.skeleton) .g-m'); const t = [...n.childNodes].find(x => x.nodeType === 3 || x.nodeName === 'B') ;
      const r = document.createRange(); r.selectNodeContents(n); const s = getSelection(); s.removeAllRanges(); s.addRange(r); }""")
    pg.wait_for_selector(".sel-tr:not(.hidden)", timeout=5000)
    pg.screenshot(path=str(out / "3_selection_button.png"))
    pg.click(".sel-tr")
    pg.wait_for_function("document.querySelector('.tr-pop .tp-out') && !/翻译中/.test(document.querySelector('.tr-pop .tp-out').textContent)", timeout=60000)
    pg.screenshot(path=str(out / "4_selection_translated.png"))
    pg.mouse.click(200, 120)
    card.locator('.actions [data-act="detail"]').click()
    pg.wait_for_selector("#sheet:not(.hidden) .sheet-tr", timeout=10000)
    pg.click("#sheet .sheet-tr")
    pg.wait_for_function("document.querySelector('#sheet .sheet-tr').textContent === '原文'", timeout=60000)
    time.sleep(0.5)
    pg.screenshot(path=str(out / "5_sheet_translated.png"))
    b.close()
print("ok")
