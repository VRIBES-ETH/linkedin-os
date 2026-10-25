"""Renders docs/banner.html to docs/banner.png (1280x640, 2x). Needs: pip install playwright && playwright install chromium."""
import subprocess, sys, time, socket
from pathlib import Path
from playwright.sync_api import sync_playwright

docs = Path(__file__).resolve().parent
port = 8766
srv = subprocess.Popen([sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1"], cwd=docs, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    for _ in range(50):
        try:
            socket.create_connection(("127.0.0.1", port), timeout=0.2).close(); break
        except OSError:
            time.sleep(0.1)
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1280, "height": 640}, device_scale_factor=2)
        pg.goto(f"http://127.0.0.1:{port}/banner.html")
        pg.wait_for_selector("body[data-ready='1']", timeout=30000)
        pg.wait_for_timeout(300)
        pg.screenshot(path=str(docs / "banner.png"))
        b.close()
finally:
    srv.terminate()
print("ok", docs / "banner.png")
