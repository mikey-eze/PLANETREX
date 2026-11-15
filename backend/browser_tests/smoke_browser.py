"""Real Chromium desktop/mobile smoke test of deployed FastAPI browser UI.

Uses the real local backend and the committed science result. External texture
requests may fail without invalidating navigation; never fake the page itself.
"""
import os
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT=Path("artifacts")
ROOT.mkdir(exist_ok=True)
BASE="http://127.0.0.1:10000"


def check_layout(page,device):
    page.goto(BASE+"/explorer",wait_until="domcontentloaded",timeout=25000)
    page.locator("#locations .location").first.wait_for(timeout=20000)
    canvas=page.locator("#globe")
    stage=page.locator(".stage")
    assert canvas.is_visible()
    a=stage.bounding_box();b=canvas.bounding_box()
    assert a and b and b["width"]>150 and b["height"]>150
    cx=a["x"]+a["width"]/2;cy=a["y"]+a["height"]/2
    gcx=b["x"]+b["width"]/2;gcy=b["y"]+b["height"]/2
    assert abs(cx-gcx)<=12, f"{device} horizontal globe offset {cx-gcx}"
    assert abs(cy-gcy)<=12, f"{device} vertical globe offset {cy-gcy}"
    assert b["x"]>=a["x"]-3 and b["y"]>=a["y"]-3, f"{device} globe clipped on top/left"
    assert b["x"]+b["width"]<=a["x"]+a["width"]+3, f"{device} globe clipped on right"
    assert b["y"]+b["height"]<=a["y"]+a["height"]+3, f"{device} globe clipped on bottom"
    size=page.evaluate("({h:document.documentElement.scrollHeight,v:window.innerHeight})")
    assert size["h"]>size["v"]+50, f"{device} page cannot scroll"
    page.screenshot(path=str(ROOT/f"{device}-moon.png"),full_page=False)
    page.locator("#mars-tab").click()
    page.locator("#page-heading").get_by_text("Explore Mars").wait_for(timeout=15000)
    page.locator("#locations .location").filter(has_text="Jezero Crater").first.click()
    page.locator("#page-heading").get_by_text("Earth counterparts").wait_for(timeout=15000)
    page.locator("#locations .location").first.wait_for(timeout=15000)
    panel=page.locator("#details")
    assert panel.is_visible()
    page.wait_for_function("document.getElementById('details').textContent.includes('Terrain distance')",timeout=20000)
    assert "Not a physical similarity %" in panel.inner_text()
    page.screenshot(path=str(ROOT/f"{device}-mars-earth.png"),full_page=False)
    page.locator("#back-button").click()
    page.locator("#globe-name").get_by_text("MARS").wait_for(timeout=15000)
    print(f"{device}: centered globe, no clipping, scroll, Moon/Mars->Earth navigation and ranking PASS")


with sync_playwright() as p:
    browser=p.chromium.launch(headless=True,args=["--disable-dev-shm-usage"])
    for label,viewport in [
        ("desktop",{"width":1366,"height":768}),
        ("mobile",{"width":390,"height":844}),
    ]:
        page=browser.new_page(viewport=viewport,device_scale_factor=1)
        try:
            check_layout(page,label)
        finally:
            page.close()
    browser.close()
