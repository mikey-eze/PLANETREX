"""End-to-end Chromium checks for PLANETREX Mission Observatory."""
import os
import subprocess
import time
from pathlib import Path

import httpx
from playwright.sync_api import sync_playwright

HERE=Path(__file__).resolve().parents[1]
HOST="http://127.0.0.1:19992"
SHOTS=Path(os.environ.get("PLAYWRIGHT_SCREENSHOTS",str(HERE/"browser-shots")))
SHOTS.mkdir(parents=True,exist_ok=True)

def ready():
    try:return httpx.get(HOST+"/health",timeout=1).status_code==200
    except httpx.HTTPError:return False

def check():
    proc=subprocess.Popen(["python","-m","uvicorn","app.main:app","--host","127.0.0.1","--port","19992"],
                          cwd=HERE,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
    try:
        for _ in range(55):
            if ready():break
            if proc.poll() is not None:
                raise RuntimeError("Backend exited: "+proc.stderr.read().decode("utf-8","replace")[-2000:])
            time.sleep(.3)
        else:raise RuntimeError("FastAPI did not start for observatory browser tests")
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=True)
            for label,viewport in [("desktop",{"width":1440,"height":900}),
                                   ("mobile",{"width":390,"height":844})]:
                page=browser.new_page(viewport=viewport,device_scale_factor=1)
                problems=[]
                page.on("pageerror",lambda error:problems.append(str(error)))
                page.goto(HOST+"/observatory",wait_until="domcontentloaded")
                page.locator("#target-sites button").first.wait_for(timeout=16000)
                page.locator("#candidate-list .candidate").first.wait_for(timeout=16000)
                assert page.locator("#target-globe").is_visible()
                assert page.locator("#earth-globe").is_visible()
                assert page.locator("#target-relief").inner_text()!="—"
                assert page.locator("#earth-relief").inner_text()!="—"
                for kind in ("target","earth"):
                    canvas=page.locator("#"+kind+"-globe").bounding_box()
                    region=page.locator("#"+kind+"-window").bounding_box()
                    assert canvas and region
                    assert canvas["y"]>=region["y"]-2
                    assert canvas["y"]+canvas["height"]<=region["y"]+region["height"]+2,kind+" globe clipped"
                    assert canvas["x"]>=region["x"]-2
                    assert canvas["x"]+canvas["width"]<=region["x"]+region["width"]+2
                stages=page.locator("#stages").bounding_box()
                sidebar=page.locator("#telemetry").bounding_box()
                assert stages and sidebar, "Missing globe stages or information sidebar"
                if label=="desktop":
                    assert sidebar["x"] >= stages["x"]+stages["width"]-3, "Telemetry must be BESIDE globes"
                    assert abs(sidebar["y"]-stages["y"])<3, "Sidebar must start level with globes"
                else:
                    assert sidebar["y"] >= stages["y"]+stages["height"]-3, "Mobile sidebar must follow globes"
                page.screenshot(path=str(SHOTS/(label+"-observatory-dual.png")),full_page=True)
                page.locator("#mode-target").click()
                assert page.locator("#target-globe").is_visible()
                assert not page.locator("#earth-globe").is_visible()
                page.locator("#mode-earth").click()
                assert not page.locator("#target-globe").is_visible()
                assert page.locator("#earth-globe").is_visible()
                page.locator("#mode-dual").click()
                page.locator("#target-mars").click()
                page.locator("#target-sites button").first.wait_for(timeout=15000)
                page.locator("#candidate-list .candidate").first.wait_for(timeout=18000)
                assert "Mars" in page.locator("#target-title").inner_text()
                assert page.locator("#candidate-count").inner_text().split()[0]!="0"
                page.locator("#domain-filters [data-domain='isru']").click()
                assert page.locator("#candidate-list").inner_text().find("No verified ISRU")!=-1
                page.locator("#domain-filters [data-domain='all']").click()
                assert page.locator("#candidate-list .candidate").count()>=1
                page.locator("#candidate-list .candidate").last.click()
                page.locator("#drawer-toggle").click()
                assert not page.locator("#telemetry-body").is_visible()
                page.locator("#drawer-toggle").click()
                assert page.locator("#telemetry-body").is_visible()
                page.locator("#orbit-switch").click()
                assert page.locator("#orbit-switch").get_attribute("aria-pressed")=="true"
                page.locator("#orbit-switch").click()
                page.screenshot(path=str(SHOTS/(label+"-observatory-mars.png")),full_page=True)
                assert not problems,problems
                assert page.evaluate("document.documentElement.scrollHeight>window.innerHeight")
                page.close()
            browser.close()
        print("PASS: PLANETREX dual globe, target/earth views, ranking, filtering, orbit, drawer and responsive canvas")
    finally:
        proc.terminate()
        try:proc.wait(timeout=10)
        except subprocess.TimeoutExpired:proc.kill()

if __name__=="__main__":check()
