"""Browser-level smoke test: responsive globe, scrolling, two planets, true ranking API.

Executed by GitHub Actions against a locally served production-equivalent
FastAPI app and the committed measured science dataset.
"""
import os
from pathlib import Path
import subprocess
import time

import httpx
from playwright.sync_api import sync_playwright

BASE="http://127.0.0.1:19991"
HERE=Path(__file__).resolve().parents[1]
ARTIFACT=Path(os.environ.get("PLAYWRIGHT_SCREENSHOTS",str(HERE/"browser-shots")))
ARTIFACT.mkdir(parents=True,exist_ok=True)


def server_ready()->bool:
    try:
        return httpx.get(BASE+"/health",timeout=1).status_code==200
    except httpx.HTTPError:
        return False


def main():
    server=subprocess.Popen(["python","-m","uvicorn","app.main:app","--host","127.0.0.1","--port","19991"],
                            cwd=HERE,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
    try:
        for _ in range(55):
            if server_ready():break
            if server.poll() is not None:
                raise RuntimeError("Backend exited before browser test")
            time.sleep(0.4)
        else:
            raise TimeoutError("Backend failed to become ready")
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=True)
            for device,viewport in [("desktop",{"width":1440,"height":900}),
                                    ("mobile",{"width":390,"height":844})]:
                page=browser.new_page(viewport=viewport,device_scale_factor=1)
                page_errors=[]
                page.on("pageerror",lambda exc:page_errors.append(str(exc)))
                page.goto(BASE+"/explorer",wait_until="domcontentloaded")
                page.locator("#locations .location").first.wait_for(timeout=18000)
                assert page.locator("#globe").is_visible()
                bounds=page.locator("#globe").bounding_box()
                stage=page.locator(".stage").bounding_box()
                assert bounds and stage, "Globe and stage must have bounding boxes"
                assert bounds["y"]>=stage["y"]-1
                assert bounds["y"]+bounds["height"]<=stage["y"]+stage["height"]+1, "Globe clipped vertically"
                assert bounds["x"]>=stage["x"]-1
                assert bounds["x"]+bounds["width"]<=stage["x"]+stage["width"]+1
                assert page.evaluate("document.documentElement.scrollHeight > window.innerHeight"),"Page cannot scroll"
                page.get_by_role("button",name="Hadley Rille").click()
                page.locator("#locations .location").first.wait_for(timeout=16000)
                assert "Earth" in page.locator("#page-heading").inner_text()
                assert page.locator("#details").inner_text().find("terrain")!=-1
                page.screenshot(path=str(ARTIFACT/f"{device}-moon-to-earth.png"),full_page=True)
                page.locator("#mars-tab").click()
                page.locator("#locations .location").first.wait_for(timeout=15000)
                page.get_by_role("button",name="Jezero Crater").click()
                page.locator("#locations .location").first.wait_for(timeout=16000)
                assert "Earth" in page.locator("#page-heading").inner_text()
                assert "MRO CTX" in page.locator("#details").inner_text()
                page.screenshot(path=str(ARTIFACT/f"{device}-mars-to-earth.png"),full_page=True)
                assert not page_errors, f"Unhandled JavaScript errors: {page_errors}"
                page.close()
            browser.close()
        print("Browser verified: desktop/mobile, scroll, globe containment, Moon/Mars -> Earth, no JS errors")
    finally:
        server.terminate()
        try:server.wait(timeout=10)
        except subprocess.TimeoutExpired:server.kill()


if __name__=="__main__":
    main()
